#!/usr/bin/env python3
"""
Analyseur edge : détecte les anomalies dans la télémétrie locale et produit
des alertes que le contrôleur envoie immédiatement sur le topic d'alerte.

Il ne parle jamais au réseau (pas de certificat) :
  - lit    telemetry_logs  (écrit par les log_parser)
  - écrit  alerts          (lu puis vidé par le contrôleur)
  - écrit  analyzer_state  (checkpoint + heartbeat : le contrôleur ne supprime
                            une ligne de télémétrie qu'une fois analysée)

Règles (une alerte par épisode, pas une par échantillon) :
  overheat_predicted  température > consigne + marge ET en hausse    -> critical
  error               nouveau(x) bit(s) dans error_code              -> critical (surchauffe / OOM) ou info
  degraded            passage en statut "degraded"                   -> warning
  silent / resumed    aucune donnée d'une machine depuis SILENCE_TIMEOUT s
"""

import json
import os
import sqlite3
import sys
import time

DB_PATH = os.environ.get("DB_PATH", "/shared/iot_data.db")
POLL_INTERVAL = float(os.environ.get("POLL_INTERVAL", 1.0))
BATCH_LIMIT = int(os.environ.get("BATCH_LIMIT", 500))            # lignes lues max par itération

TARGET_TEMP_C = float(os.environ.get("TARGET_TEMP_C", 94.0))      # consigne de la machine
TEMP_MARGIN_C = float(os.environ.get("TEMP_MARGIN_C", 1.5))       # bruit normal : ±0.3 °C
CRITICAL_TEMP_C = float(os.environ.get("CRITICAL_TEMP_C", 112.0)) # seuil de l'erreur overheat
WARN_FREE_BYTES = int(os.environ.get("WARN_FREE_BYTES", 15000))   # seuil "degraded" mémoire
SILENCE_TIMEOUT = float(os.environ.get("SILENCE_TIMEOUT", 20.0))  # s sans donnée => machine muette

# États où le chauffage est piloté : une température au-dessus de la consigne y est anormale
HEATED_STATES = {"preheat", "standby", "brewing", "updating", "degraded"}

# Bit d'error_code -> (nom, sévérité)
ERROR_BITS = {
    1: ("overheat", "critical"),
    2: ("out_of_memory", "critical"),
    4: ("capsule_jam", "info"),
    8: ("no_water", "info"),
    16: ("no_capsule", "info"),
}

JSON_SEP = (",", ":")


def parse_row(raw):
    """Ligne CSV du simulateur -> dict. Lève ValueError si le format est invalide."""
    ts, dev, _uptime, temp, _power, heap, status, err = raw.split(",")
    return {
        "timestamp": int(ts),
        "device_id": dev,
        "temperature_c": float(temp),
        "heap_free_bytes": int(heap),
        "device_status": status,
        "error_code": int(err),
    }


class DeviceDetector:
    """État et règles de détection pour une seule machine."""

    def __init__(self, device_id):
        self.device_id = device_id
        self.prev = None              # échantillon précédent
        self.overheat_flagged = False # alerte surchauffe déjà émise pour cet épisode
        self.memory_flagged = False   # alerte mémoire déjà émise pour cet épisode
        self.silent = False

    def _alert(self, ts, alert_type, severity, **fields):
        return {"device_id": self.device_id, "timestamp": ts, "type": alert_type,
                "severity": severity, **fields}

    def check(self, row):
        alerts = []
        prev = self.prev
        ts, temp = row["timestamp"], row["temperature_c"]
        status, err = row["device_status"], row["error_code"]

        if self.silent:
            silent_s = round((ts - prev["timestamp"]) / 1000)
            alerts.append(self._alert(ts, "resumed", "info", silent_s=silent_s))
            self.silent = False

        # 1. Surchauffe imminente : au-dessus de la consigne et en hausse.
        #    Le drapeau n'est levé qu'une fois la température redescendue,
        #    pour n'émettre qu'une alerte par épisode.
        above = temp > TARGET_TEMP_C + TEMP_MARGIN_C
        if above and not self.overheat_flagged and status in HEATED_STATES \
                and prev and temp > prev["temperature_c"]:
            dt = (ts - prev["timestamp"]) / 1000
            if dt > 0:
                slope = (temp - prev["temperature_c"]) / dt   # °C/s
                alerts.append(self._alert(
                    ts, "overheat_predicted", "critical", temperature_c=temp,
                    eta_s=round((CRITICAL_TEMP_C - temp) / slope)))
                self.overheat_flagged = True
        elif not above:
            self.overheat_flagged = False

        # 2. Nouvelles erreurs (front montant des bits uniquement).
        new_bits = err & ~(prev["error_code"] if prev else 0)
        if new_bits:
            hits = [(name, sev) for bit, (name, sev) in ERROR_BITS.items() if new_bits & bit]
            severity = "critical" if any(sev == "critical" for _, sev in hits) else "info"
            alerts.append(self._alert(
                ts, "error", severity, errors=[name for name, _ in hits], error_code=err,
                temperature_c=temp, heap_free_bytes=row["heap_free_bytes"]))

        # 3. Passage en "degraded" (alerte précoce du firmware). Côté mémoire, le
        #    statut alterne avec updating/off/booting tant que la fuite persiste :
        #    une seule alerte jusqu'à ce que le heap remonte (reset après OOM).
        heap = row["heap_free_bytes"]
        if status == "degraded" and (prev is None or prev["device_status"] != "degraded"):
            cause = "temperature" if above else "memory"
            if cause == "temperature" or not self.memory_flagged:
                alerts.append(self._alert(
                    ts, "degraded", "warning", cause=cause, temperature_c=temp,
                    heap_free_bytes=heap))
            if cause == "memory":
                self.memory_flagged = True
        if heap > WARN_FREE_BYTES:
            self.memory_flagged = False

        self.prev = row
        return alerts

    def check_silence(self, now_ms):
        """Machine muette : aucune ligne depuis plus de SILENCE_TIMEOUT secondes."""
        if self.silent or self.prev is None:
            return []
        if now_ms - self.prev["timestamp"] > SILENCE_TIMEOUT * 1000:
            self.silent = True
            return [self._alert(now_ms, "silent", "warning", last_seen=self.prev["timestamp"])]
        return []


def table_exists(conn, name):
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)
    ).fetchone() is not None


def init_db(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            payload TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS analyzer_state (
            id INTEGER PRIMARY KEY CHECK (id = 0),   -- une seule ligne
            last_id INTEGER NOT NULL,                -- dernier id de telemetry_logs analysé
            heartbeat REAL NOT NULL                  -- epoch s de la dernière itération
        );
    """)


def load_checkpoint(conn):
    row = conn.execute("SELECT last_id FROM analyzer_state WHERE id = 0").fetchone()
    return row[0] if row else 0


def main():
    print(f"[*] Analyseur edge démarré, base : {DB_PATH}", file=sys.stderr)

    # La table de télémétrie est créée par les log_parser : on l'attend.
    while True:
        if os.path.exists(DB_PATH):
            conn = sqlite3.connect(DB_PATH)
            if table_exists(conn, "telemetry_logs"):
                break
            conn.close()
        time.sleep(1)

    init_db(conn)
    last_id = load_checkpoint(conn)
    detectors = {}
    print(f"[*] Reprise après la ligne {last_id}", file=sys.stderr)

    try:
        while True:
            rows = conn.execute(
                "SELECT id, raw_data FROM telemetry_logs WHERE id > ? ORDER BY id LIMIT ?",
                (last_id, BATCH_LIMIT),
            ).fetchall()

            alerts = []
            for row_id, raw in rows:
                last_id = row_id
                try:
                    row = parse_row(raw)
                except ValueError:
                    print(f"[-] Ligne ignorée (format invalide) : {raw!r}", file=sys.stderr)
                    continue
                detector = detectors.get(row["device_id"])
                if detector is None:
                    detector = detectors[row["device_id"]] = DeviceDetector(row["device_id"])
                alerts += detector.check(row)

            # Silence vérifié seulement une fois le retard rattrapé, sinon les
            # vieilles lignes d'un backlog déclencheraient de fausses alertes.
            caught_up = len(rows) < BATCH_LIMIT
            if caught_up:
                now_ms = int(time.time() * 1000)
                for detector in detectors.values():
                    alerts += detector.check_silence(now_ms)

            # Alertes + checkpoint dans la même transaction : après un crash,
            # une ligne n'est jamais analysée deux fois ni oubliée.
            with conn:
                conn.executemany(
                    "INSERT INTO alerts (payload) VALUES (?)",
                    [(json.dumps(a, separators=JSON_SEP),) for a in alerts],
                )
                conn.execute(
                    "INSERT OR REPLACE INTO analyzer_state (id, last_id, heartbeat) VALUES (0, ?, ?)",
                    (last_id, time.time()),
                )

            for a in alerts:
                print(f"[!] {a['severity'].upper()} {a['device_id']} {a['type']} {a}", file=sys.stderr)

            if caught_up:
                time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        pass
    finally:
        conn.close()


if __name__ == "__main__":
    main()
