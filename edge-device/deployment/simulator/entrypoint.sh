#!/bin/sh
WORKER_INDEX=$(echo $WORKER_ID | awk -F'-' '{print $NF}')

python /app/device_simulator.py --config config.yaml --ground-truth ground_truth.log --number $WORKER_INDEX | python /app/log_parser.py