import os
from decimal import Decimal

import boto3

table = boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])
RETENTION_S = int(os.environ.get("RETENTION_DAYS", "360")) * 86400


def lambda_handler(event, context):
    gateway = event.get("gateway", "unknown")
    rows = event.get("rows", [])
    written, skipped = 0, 0

    # batch_writer groups the writes into BatchWriteItem calls (max 25 items each)
    # overwrite_by_pkeys: if a batch contains the same key twice, keep only the last one
    with table.batch_writer(overwrite_by_pkeys=["device_id", "timestamp"]) as bw:
        for line in rows:
            try:
                ts, dev, up, temp, pwr, heap, status, err = line.split(",")
                item = {
                    "device_id": dev,
                    "timestamp": int(ts),                    # epoch ms (sort key)
                    "uptime_ms": int(up),
                    "temperature_c": Decimal(temp),          # boto3 rejects float -> Decimal
                    "power_consumption_mw": Decimal(pwr),
                    "heap_free_bytes": int(heap),
                    "device_status": status,
                    "error_code": int(err),
                    "gateway": gateway,
                    "ttl": int(ts) // 1000 + RETENTION_S,    # epoch SECONDS for DynamoDB TTL
                }
            except (ValueError, ArithmeticError):
                print(f"[-] Ligne ignorée (format invalide) : {line!r}")
                skipped += 1
                continue
            bw.put_item(Item=item)
            written += 1

    print(f"[+] {gateway} : {written} lignes écrites, {skipped} ignorées")
    return {"written": written, "skipped": skipped}
