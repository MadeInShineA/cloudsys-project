#!/bin/sh
WORKER_INDEX=$(echo $WORKER_ID | awk -F'-' '{print $NF}')

# 1. Lance le parser en arrière-plan pour surveiller le fichier log
python3 -u /app/log_parser.py &

# 2. Lance le simulateur en redirigeant sa sortie vers le fichier log tampon
python /app/device_simulator.py --config config.yaml --ground-truth ground_truth.log --number $WORKER_INDEX > /shared/worker-$WORKER_INDEX.log 2>&1