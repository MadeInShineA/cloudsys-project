import json
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import boto3

sns = boto3.client("sns")
TOPIC_ARN = os.environ["SNS_TOPIC_ARN"]
CRITICAL_TEMP_C = float(os.environ.get("CRITICAL_TEMP_C", "112"))

try:
    TZ = ZoneInfo(os.environ.get("TIMEZONE", "Europe/Zurich"))
except ZoneInfoNotFoundError:
    TZ = timezone.utc

TITLES = {
    "overheat_predicted": "Overheat predicted",
    "error": "Error",
    "degraded": "Degraded",
    "silent": "Machine silent",
    "resumed": "Machine back online",
    "oom_predicted": "Out of memory predicted",
}

ERROR_TITLES = {
    "overheat": "Overheat",
    "out_of_memory": "Out of memory",
    "capsule_jam": "Capsule jam",
    "no_water": "No water",
    "no_capsule": "No capsule",
}

ERROR_TEXT = {
    "overheat": "overheat (heater did not cut off)",
    "out_of_memory": "out of memory (machine will reboot)",
    "capsule_jam": "capsule jam",
    "no_water": "water tank empty",
    "no_capsule": "no capsule detected",
}


def fmt_time(ts_ms):
    return datetime.fromtimestamp(ts_ms / 1000, TZ).strftime("%Y-%m-%d %H:%M:%S %Z")


def describe(a):
    """Phrase lisible selon le type d'alerte."""
    t = a.get("type")
    if t == "overheat_predicted":
        return (f"Temperature is {a.get('temperature_c')} °C and rising. The overheat limit "
                f"({CRITICAL_TEMP_C:g} °C) is expected in about {a.get('eta_s')} s.")
    if t == "error":
        errors = ", ".join(ERROR_TEXT.get(e, e) for e in a.get("errors", []))
        return (f"The machine reported: {errors}. Temperature {a.get('temperature_c')} °C, "
                f"free memory {a.get('heap_free_bytes')} bytes.")
    if t == "degraded":
        if a.get("cause") == "memory":
            return (f"Free memory is low ({a.get('heap_free_bytes')} bytes). "
                    "The next firmware update will probably crash the machine.")
        return f"Temperature is abnormally high ({a.get('temperature_c')} °C)."
    if t == "silent":
        return f"No data received since {fmt_time(a['last_seen'])}."
    if t == "resumed":
        return f"Data is arriving again after {a.get('silent_s')} s of silence."
    if t == "oom_predicted":
        left = a.get("updates_left", 1)
        which = "the next firmware update" if left == 1 else f"firmware update {left} from now"
        text = (f"Free memory is {a.get('value')} bytes. The machine is expected to crash "
                f"(out of memory) during {which}.")
        if a.get("predicted_oom_ts"):
            text += (f" Predicted crash: {fmt_time(a['predicted_oom_ts'])} "
                     f"(in about {round(a.get('eta_s', 0) / 60)} min).")
        return text
    return "Unknown alert type, see the raw alert below."


def lambda_handler(event, context):
    device = event.get("device_id", "unknown device")
    severity = str(event.get("severity", "unknown")).upper()
    title = TITLES.get(event.get("type"), event.get("type", "Alert"))
    if event.get("type") == "error" and event.get("errors"):
        # "Error: Overheat", ou "Error: Overheat + Capsule jam" si plusieurs bits
        title += ": " + " + ".join(ERROR_TITLES.get(e, e) for e in event["errors"])
    when = fmt_time(event["timestamp"]) if "timestamp" in event else "unknown time"

    subject = f"[{severity}] {device}: {title}"[:100]   # limite SNS : 100 caractères
    body = "\n".join([
        f"An alert was raised on machine {device} at {when}.",
        "",
        f"Type:      {title}",
        f"Severity:  {severity}",
        f"Gateway:   {event.get('gateway', 'unknown')}",
        "",
        describe(event),
        "",
        "Raw alert:",
        json.dumps(event, indent=2),
    ])

    sns.publish(TopicArn=TOPIC_ARN, Subject=subject, Message=body)
    print(f"[+] Email envoyé : {subject}")
    return {"subject": subject}
