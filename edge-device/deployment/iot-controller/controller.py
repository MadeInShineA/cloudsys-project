#!/usr/bin/env python3

import argparse
import glob
import os
import selectors
import time

def main():
    parser = argparse.ArgumentParser(description="IoT Central Controller")
    parser.add_argument("--fifo_path", default="/shared", help="Path where FIFOs are located")
    args = parser.parse_args()

    # Initialisation du sélecteur (epoll sous Linux)
    sel = selectors.DefaultSelector()
    registered_files = set()

    print(f"[*] Contrôleur démarré. Surveillance du dossier : {args.fifo_path}")

    try:
        while True:
            # 1. Découverte dynamique des fichiers FIFO (ex: fifo-0, fifo-1, etc.)
            search_pattern = os.path.join(args.fifo_path, "fifo-*")
            current_fifos = glob.glob(search_pattern)

            for fifo_path in current_fifos:
                if fifo_path not in registered_files:
                    try:
                        # SECRET : os.O_NONBLOCK évite que l'ouverture ne bloque 
                        # en attendant qu'un écrivain se connecte.
                        fd = os.open(fifo_path, os.O_RDONLY | os.O_NONBLOCK)
                        
                        # On transforme le descripteur de fichier en objet fichier Python
                        file_obj = open(fd, 'r', encoding='utf-8', errors='ignore')
                        
                        # On enregistre le fichier dans le sélecteur
                        sel.register(file_obj, selectors.EVENT_READ, data=fifo_path)
                        registered_files.add(fifo_path)
                        print(f"[+] Nouveau FIFO détecté et connecté : {fifo_path}")
                        
                    except OSError:
                        # Le fichier est peut-être en cours de création, on réessaiera au prochain tour
                        pass

            # 2. On écoute les événements sur tous les FIFO enregistrés 
            # (timeout=1.0 permet de reboucler pour chercher de nouveaux fichiers toutes les secondes)
            events = sel.select(timeout=1.0)
            
            for key, mask in events:
                file_obj = key.fileobj
                fifo_path = key.data
                
                # Lecture non bloquante de la ligne reçue
                line = file_obj.readline()
                if line:
                    print(f"[{fifo_path}] Données reçues : {line.strip()}")
                else:
                    # Si le fichier renvoie une chaîne vide, l'écrivain s'est déconnecté
                    print(f"[-] Déconnexion ou fin de flux sur {fifo_path}")
                    sel.unregister(file_obj)
                    file_obj.close()
                    registered_files.remove(fifo_path)

    except KeyboardInterrupt:
        print("\n[*] Arrêt du contrôleur...")
    finally:
        sel.close()

if __name__ == "__main__":
    main()