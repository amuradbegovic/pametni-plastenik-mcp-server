import os
import threading
import time

import paho.mqtt.client as mqtt
from mcp.server.fastmcp import FastMCP

MQTT_HOST = os.environ.get("US_MQTT_HOST", "195.130.59.221")
MQTT_PORT = int(os.environ.get("US_MQTT_PORT", "1883"))
TIM = os.environ.get("US_TIM", "tim67")

mcp = FastMCP("us-uredjaji")

mqtt_client = mqtt.Client(
    callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    client_id=f"mcp-{TIM}-{os.getpid()}",
)

# Spremiste posljednjih primljenih poruka po topic-u.
posljednje_poruke = {}
brava = threading.Lock()


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print(f"[MQTT] Povezan na {MQTT_HOST}:{MQTT_PORT}")
        client.subscribe("tele/+/SENSOR")
        client.subscribe("stat/+/RESULT")
        client.subscribe(f"etf/us/2026/{TIM}/+/data")
    else:
        print(f"[MQTT] Greska pri povezivanju, kod: {reason_code}")


def on_message(client, userdata, msg):
    payload = msg.payload.decode("utf-8", errors="replace")
    with brava:
        posljednje_poruke[msg.topic] = {
            "payload": payload,
            "vrijeme": time.time(),
        }
    print(f"[MQTT] {msg.topic} -> {payload}")


mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message
