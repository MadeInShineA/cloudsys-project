#!/usr/bin/env python3

import json
import sqlite3
import time
import os
import paho.mqtt.client as mqtt

# Récupération des paramètres via les variables d'environnement (avec valeurs par défaut)
DB_PATH = os.environ.get("DB_PATH", "/shared/iot_data.db")
MAX_BYTES = int(os.environ.get("MAX_BYTES", 5000))          # AWS IoT Core facture par tranche de 5 KB
MAX_WAIT = float(os.environ.get("MAX_WAIT", 60.0))           # Âge max (s) de la plus vieille ligne avant envoi forcé
POLL_INTERVAL = float(os.environ.get("POLL_INTERVAL", 2.0))
PUBLISH_TIMEOUT = float(os.environ.get("PUBLISH_TIMEOUT", 10.0))

MQTT_HOST = os.environ.get("MQTT_HOST", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_PORT", 1883))
TOPIC = os.environ.get("TOPIC", "iot/devices/batch")
CLIENT_ID = os.environ.get("CLIENT_ID", "iot-central-controller")
GATEWAY_ID = os.environ.get("GATEWAY_ID", CLIENT_ID)

# TLS mutuel (AWS IoT Core) : activé seulement si les certificats sont fournis
CA_CERT = os.environ.get("CA_CERT")
CERT_FILE = os.environ.get("CERT_FILE")
KEY_FILE = os.environ.get("KEY_FILE")

JSON_SEP = (",", ":")  # JSON compact (sans espaces)

def get_unsent_batch(conn, max_bytes):
    """Récupère un lot de messages non envoyés dont la taille JSON finale ne dépasse pas max_bytes.
    Retourne (ids, lignes, timestamp en ms de la plus vieille ligne, lot plein ?)."""
    cursor = conn.cursor()
    cursor.execute("SELECT id, timestamp, raw_data FROM telemetry_logs WHERE sent = 0 ORDER BY id ASC")
    rows = cursor.fetchall()

    batch_ids = []
    batch_data = []
    oldest_ts = rows[0][1] if rows else None
    current_size = len(json.dumps({"gateway": GATEWAY_ID, "rows": []}, separators=JSON_SEP))
    full = False

    for row_id, _, raw_data in rows:
        line_size = len(json.dumps(raw_data)) + (1 if batch_data else 0)  # +1 pour la virgule
        if current_size + line_size > max_bytes and batch_data:
            full = True
            break
        batch_ids.append(row_id)
        batch_data.append(raw_data)
        current_size += line_size

    return batch_ids, batch_data, oldest_ts, full

def mark_as_sent(conn, batch_ids):
    """Supprime les messages de la base après confirmation de l'envoi MQTT."""
    if not batch_ids:
        return
    cursor = conn.cursor()
    placeholders = ','.join(['?'] * len(batch_ids))
    cursor.execute(f"DELETE FROM telemetry_logs WHERE id IN ({placeholders})", batch_ids)
    conn.commit()

def on_connect(client, userdata, flags, reason_code, properties):
    print(f"[*] Connecté au broker : {reason_code}")

def on_disconnect(client, userdata, flags, reason_code, properties):
    print(f"[-] Déconnecté du broker : {reason_code}")

def main():
    print(f"[*] Contrôleur démarré. Connexion au broker MQTT {MQTT_HOST}:{MQTT_PORT} (client_id={CLIENT_ID})...")
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=CLIENT_ID)
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    if CA_CERT:
        client.tls_set(ca_certs=CA_CERT, certfile=CERT_FILE, keyfile=KEY_FILE)
        print("[*] TLS mutuel activé")
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    client.loop_start()

    print(f"[*] Surveillance de la base SQLite : {DB_PATH}")

    try:
        while True:
            if not os.path.exists(DB_PATH):
                time.sleep(1)
                continue

            conn = sqlite3.connect(DB_PATH)
            batch_ids, batch_data, oldest_ts, full = get_unsent_batch(conn, MAX_BYTES)
            age = time.time() - oldest_ts / 1000 if oldest_ts else 0

            # Envoi seulement si le lot est plein ou si la plus vieille ligne attend depuis trop longtemps
            if batch_data and (full or age >= MAX_WAIT):
                payload = json.dumps({"gateway": GATEWAY_ID, "rows": batch_data}, separators=JSON_SEP)
                reason = "plein" if full else f"âge {age:.0f}s"
                print(f"[*] Envoi MQTT d'un batch de {len(batch_data)} éléments ({len(payload)} octets, {reason})...")

                # Publication avec QoS 1 (garantit la livraison)
                info = client.publish(TOPIC, payload, qos=1)
                try:
                    info.wait_for_publish(timeout=PUBLISH_TIMEOUT)  # Attend l'ACK du broker
                except (RuntimeError, ValueError) as e:
                    print(f"[-] Publication impossible : {e}")

                if info.is_published():
                    # Nettoyage de la base
                    mark_as_sent(conn, batch_ids)
                    print("[+] Batch envoyé et purgé de la base avec succès.")
                else:
                    print("[-] Pas d'ACK du broker, nouvel essai plus tard (données conservées).")
                    time.sleep(POLL_INTERVAL)
            else:
                time.sleep(POLL_INTERVAL)

            conn.close()

    except KeyboardInterrupt:
        print("\n[*] Arrêt du contrôleur.")
    finally:
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    main()
