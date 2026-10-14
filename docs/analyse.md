# Analyse de cout

## Perimetre
Combien d'apareil deplayer ?
Quelle frequnce d'envoie ?
Pendent quelle perdiode ?


## MQTT vs HTTP
|           | MQTT             | HTTP               |
| --------- | ---------------- | ------------------ |
| connexion | asynchrone       | synchrone          |
|           | Persistante      | éphémères          |
|           | Bidirectionnel   | Unidirectionnel    |
|           |                  |                    |
| Cout      |                  | En tete plus lourd |
| Autonomie | Bass consomation |                    |
|           |                  |                    |


## service AWS IOT core (EUROPE)
basic ingest roote message to other aws service
paid ingest rule 

### Connectivity
Connectivity: $0.096  (per million minutes of connection) / device

ex: (one connection * $0.096/1,000,000 minutes of connection * 525,600 minutes/year) for 24/7 = 0.050$

### Messaging
MQTT and HTTP messaging pricing

Up to 1 billion messages: $1.20 (per million messages)
Next 4 billion messages: $0.96 (per million messages)
Over 5 billion messages: $0.84 (per million messages)

You can send and receive messages up to 128 KB in size. Messages are metered in 5 KB increments. For example, an 8 KB message is metered as two messages.

ex:
one message/sec = 1.20/1,000,000 * 525,600 minutes/year * 60 secondes = 37.80$
one message/min = 1.20/1,000,000 * 525,600 minutes/year  = 0.63$

# Payload

|                      | type  | byte         | example           |
| -------------------- | ----- | ------------ | ----------------- |
| timestamp            | int   | 8   (13 str) | 1791983034644     |
| device_id            | str   | 18           | coffee-machine-01 |
| uptime_ms            | int   | 8            | 32000             |
| temperature_c        | float | 8            | 55.0              |
| power_consumption_mw | float | 8            | 1399767.0         |
| heap_free_bytes      | int   | 8            | 49893             |
| device_status        | enum  | 8 max        | updating          |
| error_code           | 5bit  | 1            | 11111             |
| tot                  |       |              |                   |


string encoded 68byte

1791983042646,coffee-machine-01,28000,52.0,1400204.6,50030,preheat,0 

format yaml  213 octets