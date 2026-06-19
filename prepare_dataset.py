"""
Priprema dataset-a iz sensor_data.xlsx za koristenje u MCP serveru
(funkcije get_optimal_conditions / get_dataset_recommendation / compare_current_vs_optimal).

sensor_data.xlsx ima 30 listova (jedan po danu), a svaki list ima kolone
po "procesu" (process1, process2, process3, process5, process6, process7, process8),
gdje su za svaki proces mjerene: Air Temperature, Relative Humidity, Light Intensity,
CO2, Soil Moisture, Soil Temperature.

Ovaj skript:
1. Ucitava sve listove i spaja ih u jedan DataFrame.
2. Pretvara "wide" format (process1..process8 kao kolone) u "long" format
   (jedan red = jedno mjerenje za jedan proces u jednom trenutku).
3. Snima rezultat kao CSV (i opcionalno SQLite), spreman da ga MCP server
   ucita JEDNOM pri pokretanju (ne treba ga slati LLM-u u kontekst!).
4. Daje primjer nearest-neighbor funkcije koju mozete zalijepiti u mcp_server.py
   kao implementaciju get_dataset_recommendation().
"""

import re
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

XLSX_PATH = "sensor_data.xlsx"          # putanja do originalnog fajla
CSV_OUT = "plastenik_dataset.csv"        # izlazni "long" CSV
SQLITE_OUT = "plastenik_dataset.db"      # izlazna SQLite baza (alternativa CSV-u)


def load_and_reshape(xlsx_path: str) -> pd.DataFrame:
    """Spaja sve listove i pretvara wide -> long format."""
    xls = pd.ExcelFile(xlsx_path)
    long_frames = []

    for sheet in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name=sheet)
        df["Time"] = pd.to_datetime(df["Time"])  # neki listovi imaju string, neki datetime

        # pronadji sve brojeve procesa iz naziva kolona (process1, process2, ...)
        process_ids = sorted(
            set(re.findall(r"process(\d+)", " ".join(df.columns))),
            key=int,
        )

        for pid in process_ids:
            cols = {
                "air_temperature": f"Air Temperature(process{pid})",
                "humidity_air": f"Relative Humidity(process{pid})",
                "light": f"Light Intensity(process{pid})",
                "co2": f"CO2(process{pid})",
                "humidity_soil": f"Soil Moisture(process{pid})",
                "soil_temperature": f"Soil Temperature(process{pid})",
            }
            sub = df[["Time"] + list(cols.values())].copy()
            sub.columns = ["time"] + list(cols.keys())
            sub["process"] = int(pid)
            sub["day"] = sheet
            long_frames.append(sub)

    long_df = pd.concat(long_frames, ignore_index=True)
    long_df = long_df.sort_values(["process", "time"]).reset_index(drop=True)
    return long_df


def save_outputs(long_df: pd.DataFrame, csv_path: str, sqlite_path: str) -> None:
    long_df.to_csv(csv_path, index=False)

    conn = sqlite3.connect(sqlite_path)
    long_df.to_sql("readings", conn, if_exists="replace", index=False)
    conn.close()


# ---------------------------------------------------------------------------
# Primjer onoga sto ide u MCP server (mcp_server.py) - nearest neighbor pretraga
# ---------------------------------------------------------------------------

FEATURE_COLS = ["air_temperature", "humidity_air", "humidity_soil", "co2", "light"]


def build_lookup(long_df: pd.DataFrame):
    """Pripremi numpy matricu i KD-tree za brzu pretragu najblizeg uvjeta.
    Ovo se zove JEDNOM pri pokretanju MCP servera, ne pri svakom upitu.
    """
    from scipy.spatial import cKDTree

    clean = long_df.dropna(subset=FEATURE_COLS).reset_index(drop=True)
    matrix = clean[FEATURE_COLS].to_numpy(dtype=float)
    tree = cKDTree(matrix)
    return clean, tree


def get_dataset_recommendation(
    clean_df: pd.DataFrame,
    tree,
    temperature: float,
    humidity_air: float,
    humidity_soil: float,
    co2: float,
    light: float,
) -> dict:
    """Ovo postaje tijelo MCP funkcije get_dataset_recommendation(...) iz specifikacije.

    Pronalazi red iz dataseta najblizi trenutnim mjerenjima (euklidska distanca
    nad normaliziranim parametrima) i vraca taj red kao preporuku.
    """
    query = np.array([temperature, humidity_air, humidity_soil, co2, light], dtype=float)
    dist, idx = tree.query(query)
    nearest = clean_df.iloc[idx]
    return {
        "matched_time": str(nearest["time"]),
        "matched_process": int(nearest["process"]),
        "distance": float(dist),
        "air_temperature": float(nearest["air_temperature"]),
        "humidity_air": float(nearest["humidity_air"]),
        "humidity_soil": float(nearest["humidity_soil"]),
        "co2": float(nearest["co2"]),
        "light": float(nearest["light"]),
    }


if __name__ == "__main__":
    if not Path(XLSX_PATH).exists():
        raise SystemExit(f"Ne postoji {XLSX_PATH} u trenutnom folderu.")

    long_df = load_and_reshape(XLSX_PATH)
    print(f"Ucitano i preoblikovano: {len(long_df)} redova, kolone: {list(long_df.columns)}")

    save_outputs(long_df, CSV_OUT, SQLITE_OUT)
    print(f"Snimljeno: {CSV_OUT} i {SQLITE_OUT}")

    clean_df, tree = build_lookup(long_df)
    example = get_dataset_recommendation(
        clean_df, tree,
        temperature=20.0, humidity_air=70.0, humidity_soil=55.0, co2=413, light=0,
    )
    print("Primjer poziva get_dataset_recommendation(20, 70, 55, 413, 0):")
    print(example)
