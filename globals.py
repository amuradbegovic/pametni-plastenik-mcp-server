import os
import sys
import json
import threading
import time
import sqlite3

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
        print(f"[MQTT] Povezan na {MQTT_HOST}:{MQTT_PORT}", file=sys.stderr)
        client.subscribe("tele/+/SENSOR")
        client.subscribe("stat/+/RESULT")
        client.subscribe("stat/+/+")
        client.subscribe(f"etf/us/2026/{TIM}/+/data")
    else:
        print(f"[MQTT] Greska pri povezivanju, kod: {reason_code}", file=sys.stderr)


# Otvori bazu

def init_db(path=None):
    # Apsolutna putanja vezana za lokaciju modula, jer Hermes pokrece
    # server iz drugog radnog direktorija (CWD != projektni direktorij),
    # pa bi relativna putanja kreirala bazu na pogresnom mjestu.
    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "statistika.db")
    # check_same_thread=False jer upis u bazu radi MQTT loop thread
    # (on_message), a konekcija se kreira u glavnom threadu.
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS Mjerenja (
            ID               INTEGER PRIMARY KEY AUTOINCREMENT,
            Datum            TEXT NOT NULL,
            Vrijeme          TEXT NOT NULL,
            VlaznostZemlje   REAL NOT NULL DEFAULT 0,
            CO2              REAL NOT NULL DEFAULT 0,
            Svjetlost        REAL NOT NULL DEFAULT 0,
            TemperaturaZraka REAL NOT NULL DEFAULT 0,
            VlaznostZraka    REAL NOT NULL DEFAULT 0,
            TackaRosista     REAL NOT NULL DEFAULT 0
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS "Rad_Pumpe" (
            "ID"	INTEGER NOT NULL UNIQUE,
            "Datum"	TEXT NOT NULL,
            "Vrijeme"	TEXT NOT NULL,
            "Trajanje_rada"	REAL NOT NULL,
            PRIMARY KEY("ID" AUTOINCREMENT)
        );
        """
    )
    conn.commit()
    return conn

statistika = init_db()
db_brava = threading.Lock()


# Dodaj mjerenje u bazu

def insert_measurement(conn, message):
    data = json.loads(message) if isinstance(message, str) else message

    date_part, time_part = data["Time"].split("T")

    analog = data.get("ANALOG", {})
    dht = data.get("DHT11", {})

    # Pretvori sirove ocitanja senzora isto kao u tasmota_tools.py:
    #   A2 -> vlaznost zemlje (%), MQ2_1 -> CO2.
    a2 = analog.get("A2", 0)

    vlaznost_zemlje = round(100 * (4000 - a2) / 2600, 2) if a2 and a2 > 0 else 0
    # Uredjaj sada sam ocitava svjetlost (ANALOG.Illuminance1) kako treba, pa se
    # sirova LDR vrijednost vise ne pretvara u lux, nego se sprema onakva kakva je.
    svjetlost = analog.get("Illuminance1", 0)

    row = (
        date_part,
        time_part,
        vlaznost_zemlje,
        analog.get("MQ2_1", 0),
        svjetlost,
        dht.get("Temperature", 0),
        dht.get("Humidity", 0),
        dht.get("DewPoint", 0),
    )

    with db_brava:
        conn.execute(
            """
            INSERT INTO Mjerenja
                (Datum, Vrijeme, VlaznostZemlje, CO2, Svjetlost,
                 TemperaturaZraka, VlaznostZraka, TackaRosista)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            row,
        )
        conn.commit()

def insert_pump_work(conn, date_part, time_part, vrijeme):
    with open("DEBUG.txt", "a") as file:
        file.write("insert_pump_work_SQL-")
    with db_brava:
        with open("DEBUG.txt", "a") as file:
            file.write("SQL_setup-")
        conn.execute(
            """
            INSERT INTO "Rad_Pumpe" 
                ("Datum", "Vrijeme", "Trajanje_rada") 
            VALUES (?, ?, ?);
            """,
            date_part,
            time_part,
            vrijeme
        )
        with open("DEBUG.txt", "a") as file:
            file.write("SQL_execute-")
        conn.commit()
        with open("DEBUG.txt", "a") as file:
            file.write("END")
    pass


def on_message(client, userdata, msg):
    payload = msg.payload.decode("utf-8", errors="replace")
    with brava:
        posljednje_poruke[msg.topic] = {
            "payload": payload,
            "vrijeme": time.time(),
        }
    # Telemetrija senzora (tele/<uredjaj>/SENSOR) -> upisi mjerenje u bazu.
    if msg.topic.startswith("tele/") and msg.topic.endswith("/SENSOR"):
        try:
            insert_measurement(statistika, payload)
        except (json.JSONDecodeError, KeyError, ValueError, sqlite3.Error) as e:
            print(f"[DB] Greska pri upisu mjerenja: {e}", file=sys.stderr)

    print(f"[MQTT] {msg.topic} -> {payload}", file=sys.stderr)


mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message
