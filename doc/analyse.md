# Analyse de cout

## service AWS IOT core (EUROPE)
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