"""
Prédiction de panne mémoire (out of memory) par machine.

Appelée par la règle de télémétrie avec le même batch que telemetry-parser.
Chaque mise à jour firmware perd une quantité fixe de heap, jusqu'au crash :
  - baseline   = heap libre "au repos" (hors brewing et erreurs)
  - step       = heap perdu par mise à jour (médiane des dernières chutes de baseline)
  - interval   = temps moyen entre deux mises à jour (appris)
  => updates_left     = nombre de mises à jour avant le crash
     predicted_oom_ts = instant estimé du crash

Un batch ne couvre que ~60 s : l'état de chaque machine est conservé dans
la table STATE_TABLE (un item par device_id), relu et réécrit à chaque batch.
Quand il ne reste qu'ALERT_AT_UPDATES_LEFT mises à jour, une alerte
oom_predicted est publiée sur le topic d'alerte (stockage + email).
"""

import json
import math
import os
import statistics
import time

import boto3

state_table = boto3.resource("dynamodb").Table(os.environ["STATE_TABLE"])
iot = boto3.client("iot-data", endpoint_url=f"https://{os.environ['IOT_ENDPOINT']}")
ALERT_TOPIC = os.environ.get("ALERT_TOPIC", "group-8/iot/devices/alert")

CRITICAL_FREE_BYTES = int(os.environ.get("CRITICAL_FREE_BYTES", "5000"))  # seuil du crash
DEFAULT_STEP_BYTES = int(os.environ.get("DEFAULT_STEP_BYTES", "8000"))    # avant le 1er apprentissage
MIN_STEP_BYTES = int(os.environ.get("MIN_STEP_BYTES", "2000"))            # chute plus petite = bruit
STEP_HISTORY_SIZE = int(os.environ.get("STEP_HISTORY_SIZE", "10"))        # chutes gardées pour la médiane
LEAK_DELAY_S = int(os.environ.get("LEAK_DELAY_S", "80"))                  # délai fuite après début d'update
ALERT_AT_UPDATES_LEFT = int(os.environ.get("ALERT_AT_UPDATES_LEFT", "1"))
MIN_INTERVAL_S = 300  # écart plus court = relance immédiate après un crash, ignoré

ERROR_BIT_OOM = 2


def parse(line):
    ts, dev, _up, _temp, _pwr, heap, status, err = line.split(",")
    return dev, int(ts), int(heap), status, int(err)


def lambda_handler(event, context):
    by_device = {}
    for line in event.get("rows", []):
        try:
            dev, ts, heap, status, err = parse(line)
        except ValueError:
            continue
        by_device.setdefault(dev, []).append((ts, heap, status, err))

    for dev, rows in by_device.items():
        process_device(dev, sorted(rows))
    return {"devices": len(by_device)}


def process_device(dev, rows):
    s = state_table.get_item(Key={"device_id": dev}).get("Item", {})

    # QoS 1 : un batch peut arriver deux fois -> on ignore les lignes déjà vues
    rows = [r for r in rows if r[0] > int(s.get("last_ts", 0))]
    if not rows:
        return

    baseline = int(s["baseline_heap"]) if "baseline_heap" in s else None
    # Dernières chutes observées ; un ancien item sans historique repart de son step_bytes
    step_history = [int(x) for x in s.get("step_history", [])]
    if "step_history" not in s and "step_bytes" in s:
        step_history = [int(s["step_bytes"])]
    interval = int(s.get("update_interval_s", 0))
    last_update = int(s.get("last_update_ts", 0))
    baseline_at_update = int(s["baseline_at_update"]) if "baseline_at_update" in s else None
    prev_status = s.get("last_status")
    notified = bool(s.get("notified", False))
    oom_count = int(s.get("oom_count", 0))

    clean = []  # heap des lignes "au repos" depuis le dernier crash du batch
    for ts, heap, status, err in rows:
        if err & ERROR_BIT_OOM:
            if prev_status != "error":
                oom_count += 1
            # Crash : le heap repart de zéro, la relance immédiate de l'update ne compte pas
            baseline, baseline_at_update, last_update, notified, clean = None, None, 0, False, []
        elif status == "updating" and prev_status != "updating":
            if last_update and (ts - last_update) / 1000 >= MIN_INTERVAL_S:
                gap = (ts - last_update) // 1000
                interval = gap if not interval else round(0.7 * interval + 0.3 * gap)
            last_update = ts
            baseline_at_update = baseline
        if status != "brewing" and err == 0:
            clean.append(heap)
        prev_status = "error" if err & ERROR_BIT_OOM else status

    if clean:
        new_baseline = max(clean)  # le brewing ne fait que baisser le heap -> max
        if baseline is not None:
            drop = baseline - new_baseline
            if drop >= MIN_STEP_BYTES:
                step_history = (step_history + [drop])[-STEP_HISTORY_SIZE:]  # fuite observée
            elif -drop >= MIN_STEP_BYTES:
                notified = False                  # heap remonté (reboot complet)
        baseline = new_baseline

    # Médiane : une chute mal mesurée (fuite à cheval sur deux batches, bruit)
    # ne fausse pas la taille de fuite. Arrondie : DynamoDB refuse les float.
    step = round(statistics.median(step_history)) if step_history else DEFAULT_STEP_BYTES

    last_ts = rows[-1][0]
    item = {
        "device_id": dev,
        "last_ts": last_ts,
        "last_status": prev_status,
        "step_bytes": step,
        "step_history": step_history,
        "update_interval_s": interval,
        "last_update_ts": last_update,
        "notified": notified,
        "oom_count": oom_count,
        "updated_at": int(time.time()),
    }
    if baseline_at_update is not None:
        item["baseline_at_update"] = baseline_at_update

    if baseline is not None:
        updates_left = max(1, math.ceil((baseline - CRITICAL_FREE_BYTES) / step))
        item["baseline_heap"] = baseline
        item["updates_left"] = updates_left

        if interval and last_update:
            # Update en cours dont la fuite n'est pas encore passée : c'est elle la prochaine
            in_pending_update = (
                prev_status == "updating"
                and baseline_at_update is not None
                and baseline_at_update - baseline < MIN_STEP_BYTES
            )
            next_update = last_update if in_pending_update else max(last_update + interval * 1000, last_ts)
            oom_ts = next_update + ((updates_left - 1) * interval + LEAK_DELAY_S) * 1000
            item["predicted_oom_ts"] = oom_ts

        if updates_left <= ALERT_AT_UPDATES_LEFT and not notified:
            alert = {
                "device_id": dev,
                "timestamp": last_ts,
                "type": "oom_predicted",
                "severity": "critical",
                "value": baseline,
                "updates_left": updates_left,
            }
            if "predicted_oom_ts" in item:
                alert["predicted_oom_ts"] = item["predicted_oom_ts"]
                alert["eta_s"] = max(0, (item["predicted_oom_ts"] - last_ts) // 1000)
            iot.publish(topic=ALERT_TOPIC, qos=1, payload=json.dumps(alert))
            print(f"[!] {dev} : alerte oom_predicted envoyée {alert}")
            item["notified"] = True

    state_table.put_item(Item=item)
    print(f"[+] {dev} : baseline={baseline} step={step} interval={interval}s "
          f"updates_left={item.get('updates_left')} predicted_oom_ts={item.get('predicted_oom_ts')}")
