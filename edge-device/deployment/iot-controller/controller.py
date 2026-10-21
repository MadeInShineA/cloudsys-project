#!/usr/bin/env python3

import argparse
import glob
import json
import os
import selectors
import time
import paho.mqtt.client as mqtt


def parse_arguments():
    """Parse et retourne les arguments de la ligne de commande."""
    parser = argparse.ArgumentParser(description="IoT Central Controller")
    parser.add_argument("--fifo-path", default="/shared", help="Path where FIFOs are located")
    parser.add_argument("--batch-size", type=int, default=30, help="Number of lines before flushing")
    parser.add_argument("--flush-interval", type=float, default=10.0, help="Max time in seconds before flushing")
    
    # Paramètres MQTT
    parser.add_argument("--mqtt-host", default="your-iot-endpoint.amazonaws.com", help="AWS IoT Endpoint")
    parser.add_argument("--mqtt-port", type=int, default=8883, help="MQTT Port (8883 for TLS)")
    parser.add_argument("--cert-path", default="/certs", help="Path to certificates directory")
    parser.add_argument("--topic", default="iot/devices/batch", help="MQTT Topic")
    
    return parser.parse_args()


def initialize_mqtt_client(args):
    """Initialise et configure le client MQTT (avec support TLS pour AWS IoT Core)."""
    client = mqtt.Client(client_id="iot-central-controller")
    
    # Configuration TLS (décommenter si les certificats sont présents)
    # client.tls_set(
    #     ca_certs=os.path.join(args.cert_path, "root-CA.crt"),
    #     certfile=os.path.join(args.cert_path, "device.pem.crt"),
    #     keyfile=os.path.join(args.cert_path, "private.pem.key")
    # )

    try:
        print(f"[*] Connexion au broker MQTT {args.mqtt_host}:{args.mqtt_port}...")
        client.connect(args.mqtt_host, args.mqtt_port, keepalive=60)
        client.loop_start()
    except Exception as e:
        print(f"[-] Erreur de connexion MQTT : {e}")
        
    return client


def discover_and_register_fifos(fifo_path, selector, registered_files):
    """Découvre dynamiquement les nouveaux fichiers FIFO et les enregistre dans le sélecteur."""
    search_pattern = os.path.join(fifo_path, "fifo-*")
    current_fifos = glob.glob(search_pattern)

    for fifo_path_item in current_fifos:
        if fifo_path_item not in registered_files:
            try:
                # Ouverture non bloquante pour éviter le blocage si aucun writer n'est présent
                fd = os.open(fifo_path_item, os.O_RDONLY | os.O_NONBLOCK)
                file_obj = open(fd, 'r', encoding='utf-8', errors='ignore')
                
                selector.register(file_obj, selectors.EVENT_READ, data=fifo_path_item)
                registered_files.add(fifo_path_item)
                print(f"[+] Connecté au nouveau FIFO : {fifo_path_item}")
            except OSError:
                # Le fichier est peut-être en cours de création, on ignore et réessaiera plus tard
                pass


def handle_fifo_read(key, selector, registered_files, data_buffer):
    """Lit les données disponibles sur un FIFO et gère les déconnexions."""
    file_obj = key.fileobj
    fifo_path = key.data
    
    line = file_obj.readline()
    if line:
        raw_data = line.strip()
        if raw_data:
            data_buffer.append(raw_data)
    else:
        # Chaîne vide = fin de flux ou déconnexion de l'écrivain
        print(f"[-] Déconnexion du FIFO : {fifo_path}")
        selector.unregister(file_obj)
        file_obj.close()
        registered_files.remove(fifo_path)


def should_flush_buffer(data_buffer, last_flush_time, batch_size, flush_interval):
    """Détermine si le buffer doit être vidé (par taille atteinte ou par délai écoulé)."""
    if not data_buffer:
        return False
        
    current_time = time.time()
    time_elapsed = current_time - last_flush_time
    
    return len(data_buffer) >= batch_size or time_elapsed >= flush_interval


def flush_buffer(data_buffer, client, topic):
    """Forme le payload JSON global, l'envoie via MQTT et réinitialise le buffer."""
    payload = json.dumps(data_buffer)
    
    print(f"\n--- [PUBLISH MQTT] Batch de {len(data_buffer)} messages (Taille : {len(payload)} octets) ---")
    print(payload[:150] + "..." if len(payload) > 150 else payload)
    print("-" * 75 + "\n")
    
    # Envoi effectif via MQTT
    client.publish(topic, payload, qos=1)
    
    data_buffer.clear()


def main():
    args = parse_arguments()
    mqtt_client = initialize_mqtt_client(args)
    
    sel = selectors.DefaultSelector()
    registered_files = set()
    data_buffer = []
    last_flush_time = time.time()

    print(f"[*] Contrôleur démarré. Surveillance de : {args.fifo_path}")

    try:
        while True:
            # 1. Gestion dynamique des sources (découverte des nouveaux workers)
            discover_and_register_fifos(args.fifo_path, sel, registered_files)python3 controller.py --mqtt-host localhost --mqtt-port 1883 --topic "iot/devices/batch"

            # 2. Multiplexage I/O non bloquant (epoll)
            events = sel.select(timeout=1.0)
            
            for key, mask in events:
                handle_fifo_read(key, sel, registered_files, data_buffer)

            # 3. Vérification et envoi du batch si les conditions sont réunies
            if should_flush_buffer(data_buffer, last_flush_time, args.batch_size, args.flush_interval):
                flush_buffer(data_buffer, mqtt_client, args.topic)
                last_flush_time = time.time()

    except KeyboardInterrupt:
        print("\n[*] Arrêt du contrôleur demandé...")
    finally:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
        sel.close()
        print("[*] Contrôleur arrêté proprement.")


if __name__ == "__main__":
    main()