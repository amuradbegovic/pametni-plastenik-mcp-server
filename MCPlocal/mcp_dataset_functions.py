"""
MCP funkcije za dataset i preporuke (sekcija 5.4 specifikacije) - "Pametni plastenik".

PRETPOSTAVKA: vec ste pokrenuli prepare_dataset.py nad sensor_data.xlsx, cime
je nastala plastenik_dataset.db (long format, tabela "readings", kolone:
time, air_temperature, humidity_air, light, co2, humidity_soil,
soil_temperature, process, day).

Ako koristite plastenik_dataset.csv umjesto .db, samo izmijenite _load_long()
da koristi pd.read_csv(CSV_PATH) - ostatak fajla se ne mijenja.

VAZNO: dataset NEMA kolonu koja kaze koja biljka raste u kojem "procesu".
Procese (1,2,3,5,6,7,8 - process4 ne postoji) morate sami mapirati na biljke
u PROCESS_PLANT_MAP nizu ispod, prema svom eksperimentu.

Zalijepite funkcije ispod u svoj mcp_server.py i (ako koristite FastMCP)
dodajte @mcp.tool() dekorator iznad svake.
"""

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import os
import sys

from globals import mcp, mqtt_client, posljednje_poruke, brava

DB_PATH = f"{os.path.dirname(os.path.abspath(sys.argv[0]))}/plastenik_dataset.db"
TABLE_NAME = "readings"

# ISPRAVITE PREMA SVOM EKSPERIMENTU:
PROCESS_PLANT_MAP = {
    1: "paradajz",
    2: "paradajz",
    3: "paprika",
    5: "paprika",
    6: "paradajz",
    7: "paprika",
    8: "paradajz",
}

FEATURES = ["air_temperature", "humidity_air", "humidity_soil", "co2", "light"]

_cache: dict = {}


def _load_long() -> pd.DataFrame:
    """Ucitava plastenik_dataset.db (long format) i kesira u memoriji.
    Poziva se samo jednom pri prvom pozivu MCP funkcije."""
    if "long_df" in _cache:
        return _cache["long_df"]

    if not Path(DB_PATH).exists():
        raise FileNotFoundError(
                f"Ne postoji {DB_PATH}, pwd javlja {os.path.dirname(os.path.abspath(sys.argv[0]))}. Pokrenite prepare_dataset.py nad sensor_data.xlsx."
        )

    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql(f"SELECT * FROM {TABLE_NAME}", conn)
    conn.close()

    df["plant_type"] = df["process"].map(PROCESS_PLANT_MAP).fillna("nepoznato")
    df = df.dropna(subset=FEATURES)

    _cache["long_df"] = df
    return df


def _filtered(plant_type: str | None) -> pd.DataFrame:
    df = _load_long()
    if plant_type:
        df = df[df["plant_type"] == plant_type]
    return df


# ---------------------------------------------------------------------------
# MCP FUNKCIJE
# ---------------------------------------------------------------------------

def get_current_working_directory() -> str:
    return os.path.dirname(os.path.abspath(sys.argv[0]))

def get_optimal_conditions(plant_type: str) -> dict:
    """Vraca optimalne (prosjecne) vrijednosti svih parametara za zadanu biljku iz dataseta."""
    df = _filtered(plant_type)
    if df.empty:
        return {"error": f"Nema podataka za plant_type='{plant_type}'. "
                          f"Provjerite PROCESS_PLANT_MAP."}
    means = df[FEATURES].mean().round(2)
    return {**means.to_dict(), "broj_mjerenja": len(df)}


def get_dataset_recommendation(
    plant_type: str,
    temperature: float,
    humidity_air: float,
    humidity_soil: float,
    co2: float,
    light: float,
) -> dict:
    """Pronalazi najblize uvjete u datasetu (za datu biljku) i vraca preporucenu
    kolicinu vode i osvjetljenja, na osnovu odstupanja trenutnih mjerenja od
    najslicnijeg historijskog uvjeta.
    """
    df = _filtered(plant_type)
    if df.empty:
        return {"error": f"Nema podataka za plant_type='{plant_type}'. "
                          f"Provjerite PROCESS_PLANT_MAP."}

    query = np.array([temperature, humidity_air, humidity_soil, co2, light], dtype=float)
    matrix = df[FEATURES].to_numpy(dtype=float)
    dists = np.linalg.norm(matrix - query, axis=1)
    idx = int(np.argmin(dists))
    nearest = df.iloc[idx]

    soil_delta = float(nearest["humidity_soil"] - humidity_soil)
    light_delta = float(nearest["light"] - light)

    if soil_delta > 5:
        zalijevanje = "potrebno zalijevanje - vlaznost tla nize od referentne"
    elif soil_delta < -5:
        zalijevanje = "zalijevanje trenutno nije potrebno"
    else:
        zalijevanje = "vlaznost tla blizu referentne - minimalno zalijevanje"

    return {
        "plant_type": plant_type,
        "matched_time": str(nearest["time"]),
        "matched_process": int(nearest["process"]),
        "distance": round(float(dists[idx]), 3),
        "referentni_uvjeti": {f: round(float(nearest[f]), 2) for f in FEATURES},
        "soil_moisture_delta": round(soil_delta, 2),
        "light_delta": round(light_delta, 2),
        "preporuka_zalijevanja": zalijevanje,
    }


def compare_current_vs_optimal(
    plant_type: str,
    temperature: float,
    humidity_air: float,
    humidity_soil: float,
    co2: float,
    light: float,
) -> dict:
    """Uporedjuje trenutna mjerenja sa optimalnim (prosjecnim) uvjetima za biljku
    i vraca odstupanja po svakom parametru.

    Napomena: specifikacija ovu funkciju definise sa samo plant_type parametrom
    (agent bi trenutna mjerenja trebao sam ocitati preko get_all_sensors()).
    Ovdje su mjerenja eksplicitni parametri da funkcija radi samostalno - ako
    vec imate get_all_sensors() u svom MCP serveru, pozovite je unutar ove
    funkcije umjesto da mjerenja primate kao argumente.
    """
    optimal = get_optimal_conditions(plant_type)
    if "error" in optimal:
        return optimal

    trenutno = {
        "air_temperature": temperature,
        "humidity_air": humidity_air,
        "humidity_soil": humidity_soil,
        "co2": co2,
        "light": light,
    }
    odstupanja = {k: round(trenutno[k] - optimal[k], 2) for k in trenutno}
    return {"trenutno": trenutno, "optimalno": optimal, "odstupanja": odstupanja}


if __name__ == "__main__":
    print("Dostupne biljke u datasetu:", set(PROCESS_PLANT_MAP.values()))
    print()
    print("get_optimal_conditions('paradajz'):")
    print(get_optimal_conditions("paradajz"))
    print()
    print("get_dataset_recommendation('paradajz', 20, 60, 50, 413, 0):")
    print(get_dataset_recommendation("paradajz", 20, 60, 50, 413, 0))
    print()
    print("compare_current_vs_optimal('paprika', 25, 40, 45, 413, 0):")
    print(compare_current_vs_optimal("paprika", 25, 40, 45, 413, 0))
