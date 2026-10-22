#!/usr/bin/env python3

import os
import sqlite3
import time
import sys

def get_env_or_exit(name):
    val = os.getenv(name)
    if not val:
        print(f"[-] Variable d'environnement {name} manquante.", file=sys.stderr)
        sys.exit(1)
    return val

def init_db(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL;")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS telemetry_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp INTEGER,
            raw_data TEXT,
            sent INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

def tail_f(filename):
    """Générateur qui lit un fichier en continu (type tail -f en Python)."""
    while not os.path.exists(filename):
        time.sleep(0.5)
        
    with open(filename, "r") as f:
        # Se positionne à la fin du fichier pour ne lire que les *nouvelles* lignes
        f.seek(0, os.SEEK_END)
        while True:
            line = f.readline()
            if not line:
                time.sleep(0.2)
                continue
            yield line

def main():
    worker_id = get_env_or_exit("WORKER_ID")
    db_path = os.getenv("DB_PATH", "/shared/iot_data.db")
    
    # Extrait l'index du worker (ex: device-worker-0 -> 0)
    worker_index = worker_id.split('-')[-1]
    log_file = f"/shared/worker-{worker_index}.log"
    
    print(f"[*] Log parser pour {worker_id} démarré. Lecture de {log_file} -> {db_path}", file=sys.stderr)
    
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        for line in tail_f(log_file):
            raw_line = line.strip()
            if not raw_line:
                continue
            
            try:
                timestamp = int(raw_line.split(',')[0])
            except (IndexError, ValueError):
                timestamp = int(time.time() * 1000)

            # Insertion sécurisée dans SQLite
            cursor.execute(
                "INSERT INTO telemetry_logs (timestamp, raw_data, sent) VALUES (?, ?, 0)",
                (timestamp, raw_line)
            )
            conn.commit()
            
    except KeyboardInterrupt:
        pass
    finally:
        conn.close()

if __name__ == "__main__":
    main()