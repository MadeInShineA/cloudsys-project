#!/usr/bin/env python3

import json
import sqlite3
import time
import os
import paho.mqtt.client as mqtt

# Récupération des paramètres via les variables d'environnement (avec valeurs par défaut)
DB_PATH = os.environ.get("DB_PATH", "/shared/iot_data.db")
MAX_BYTES = int(os.environ.get("MAX_BYTES", 4500))
POLL_INTERVAL = float(os.environ.get("POLL_INTERVAL", 2.0))

MQTT_HOST = os.environ.get("MQTT_HOST", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_PORT", 1883))
TOPIC = os.environ.get("TOPIC", "iot/devices/batch")

def get_unsent_batch(conn, max_bytes):
    """Récupère un lot de messages non envoyés dont la taille cumulée approche la limite."""
    cursor = conn.cursor()
    cursor.execute("SELECT id, raw_data FROM telemetry_logs WHERE sent = 0 ORDER BY id ASC")
    rows = cursor.fetchall()
    
    batch_ids = []
    batch_data = []
    current_size = 0
    
    for row_id, raw_data in rows:
        line_size = len(json.dumps(raw_data))
        if current_size + line_size > max_bytes and batch_data:
            break
        batch_ids.append(row_id)
        batch_data.append(raw_data)
        current_size += line_size
        
    return batch_ids, batch_data

def mark_as_sent(conn, batch_ids):
    """Supprime les messages de la base après confirmation de l'envoi MQTT."""
    if not batch_ids:
        return
    cursor = conn.cursor()
    placeholders = ','.join(['?'] * len(batch_ids))
    cursor.execute(f"DELETE FROM telemetry_logs WHERE id IN ({placeholders})", batch_ids) 
    conn.commit()

def main():
    print(f"[*] Contrôleur démarré. Connexion au broker MQTT {MQTT_HOST}:{MQTT_PORT}...")
    client = mqtt.Client(client_id="iot-central-controller")
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    client.loop_start()

    print(f"[*] Surveillance de la base SQLite : {DB_PATH}")

    try:
        while True:
            if not os.path.exists(DB_PATH):
                time.sleep(1)
                continue
                
            conn = sqlite3.connect(DB_PATH)
            batch_ids, batch_data = get_unsent_batch(conn, MAX_BYTES)
            
            if batch_data:
                payload = json.dumps(batch_data)
                print(f"[*] Envoi MQTT d'un batch de {len(batch_data)} éléments ({len(payload)} octets)...")
                
                # Publication avec QoS 1 (garantit la livraison)
                info = client.publish(TOPIC, payload, qos=1)
                info.wait_for_publish() # Attend l'ACK du broker
                
                # Nettoyage de la base
                mark_as_sent(conn, batch_ids)
                print("[+] Batch envoyé et purgé de la base avec succès.")
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