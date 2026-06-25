import json
import os
import sqlite3
from datetime import datetime

import matplotlib

matplotlib.use("Agg")  # bez GUI-ja, jer server radi bez displeja
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

from globals import mcp, statistika, db_brava, insert_pump_work

# Mapiranje naziva mjerenja na (kolona u bazi, citljiv naziv, jedinica).
MJERENJA = {
    "VlaznostZemlje": ("VlaznostZemlje", "Vlaznost zemlje", "%"),
    "CO2": ("CO2", "CO2", "ppm"),
    "Svjetlost": ("Svjetlost", "Svjetlost", "lux"),
    "TemperaturaZraka": ("TemperaturaZraka", "Temperatura zraka", "°C"),
    "VlaznostZraka": ("VlaznostZraka", "Vlaznost zraka", "%"),
    "TackaRosista": ("TackaRosista", "Tacka rosista", "°C"),
}

# Direktorij u koji se spremaju generisani grafovi.
GRAFOVI_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "grafovi")


@mcp.tool()
def statistika_sql_upit(sql: str) -> str:
    """Izvrsi SQL SELECT upit nad bazom mjerenja iz plastenika.

    Koristi ovaj alat za odgovaranje na pitanja o izmjerenim podacima,
    npr. prosjecna temperatura u nekom periodu, maksimalna vlaznost zraka,
    broj mjerenja u danu, koliko dugo je pumpa radila i slicno. Sam sastavi 
    odgovarajuci SELECT upit na osnovu opisanih kolona, pa rezultat protumaci 
    korisniku.

    Baza ima dvije tabele: 'Mjerenja' i 'Rad_Pumpe'
    
    'Mjerenja' ima kolone:
        ID               INTEGER  - redni broj zapisa
        Datum            TEXT     - datum mjerenja, format 'YYYY-MM-DD'
        Vrijeme          TEXT     - vrijeme mjerenja, format 'HH:MM:SS'
        VlaznostZemlje   REAL     - vlaznost zemlje u procentima (%)
        CO2              REAL     - koncentracija CO2
        Svjetlost        REAL     - osvjetljenje u luksima (lux)
        TemperaturaZraka REAL     - temperatura zraka (stepeni C)
        VlaznostZraka    REAL     - vlaznost zraka (%)
        TackaRosista     REAL     - tacka rosista (stepeni C)
    
    'Rad_Pumpe' ima kolone:
        ID               INTEGER  - redni broj zapisa
        Datum            TEXT     - datum mjerenja, format 'YYYY-MM-DD'
        Vrijeme          TEXT     - vrijeme mjerenja, format 'HH:MM:SS'
        Trajanje_rada    REAL     - trajanje rada pumpe u sekundama

    Dozvoljeni su samo SELECT (ili WITH) upiti; svaki drugi upit se odbija.
    Rezultat se vraca kao JSON sa kljucevima 'kolone' i 'redovi'.

    Args:
        sql: SQL SELECT naredba. Primjer za prosjecnu temperaturu u periodu:
             "SELECT AVG(TemperaturaZraka) AS prosjek FROM Mjerenja
              WHERE Datum = '2026-06-23'
                AND Vrijeme BETWEEN '17:00:00' AND '18:00:00'"
             ili
             "SELECT COUNT(Trajanje_rada) AS broj_pokretanja FROM Rad_Pumpe
              WHERE Datum = '2026-06-24'
                AND Vrijeme BETWEEN '06:00:00' AND '18:00:00'""
    """
    upit = sql.strip().rstrip(";").strip()
    prva_rijec = upit.lower()
    if not (prva_rijec.startswith("select") or prva_rijec.startswith("with")):
        return "Dozvoljeni su samo SELECT upiti."

    try:
        with db_brava:
            cur = statistika.execute(upit)
            kolone = [opis[0] for opis in cur.description] if cur.description else []
            redovi = cur.fetchall()
    except sqlite3.Error as e:
        return f"Greska pri izvrsavanju upita: {e}"

    # Ogranici broj redova da ne preplavi odgovor (agregati su uvijek mali).
    MAX_REDOVA = 500
    odsjeceno = len(redovi) > MAX_REDOVA
    redovi = redovi[:MAX_REDOVA]

    rezultat = {
        "kolone": kolone,
        "redovi": [dict(zip(kolone, red)) for red in redovi],
        "broj_redova": len(redovi),
    }
    if odsjeceno:
        rezultat["napomena"] = f"Prikazano prvih {MAX_REDOVA} redova."

    return json.dumps(rezultat, ensure_ascii=False)


@mcp.tool()
def statistika_graf(mjerenje: str, pocetak: str, kraj: str) -> str:
    """Nacrtaj graf jednog mjerenja u vremenskom domenu za zadani interval.

    Koristi ovaj alat kada korisnik trazi da se nacrta, prikaze ili posalje
    graf nekog mjerenja kroz vrijeme (npr. "nacrtaj temperaturu zraka danas",
    "posalji mi graf vlaznosti zemlje od jucer u 8h do danas u 12h").

    Alat upita bazu 'Mjerenja', nacrta vrijednost na y-osi u zavisnosti od
    vremena na x-osi, snimi sliku (PNG) na disk i vrati JSON sa kljucem
    'putanja' u kojem je apsolutna putanja do slike. Tu putanju proslijedi
    funkciji za slanje slike preko Telegrama.

    Args:
        mjerenje: Koje mjerenje crtati. Dozvoljene vrijednosti su:
            'VlaznostZemlje', 'CO2', 'Svjetlost', 'TemperaturaZraka',
            'VlaznostZraka', 'TackaRosista'.
        pocetak: Pocetak intervala, format 'YYYY-MM-DD HH:MM:SS'
                 (vrijeme je opciono, npr. '2026-06-23' znaci od pocetka dana).
        kraj: Kraj intervala, isti format kao 'pocetak'
              (npr. '2026-06-23' znaci do kraja dana).

    Returns:
        JSON sa kljucem 'putanja' (apsolutna putanja do PNG slike) i
        'broj_tacaka', ili 'greska' ako nesto nije u redu.
    """
    if mjerenje not in MJERENJA:
        return json.dumps(
            {"greska": f"Nepoznato mjerenje '{mjerenje}'. "
                       f"Dozvoljeno: {', '.join(MJERENJA)}."},
            ensure_ascii=False,
        )
    kolona, naziv, jedinica = MJERENJA[mjerenje]

    # Normalizuj granice intervala u puni 'YYYY-MM-DD HH:MM:SS' oblik tako da
    # poredjenje 'Datum || " " || Vrijeme' radi leksikografski ispravno.
    od = pocetak.strip()
    do = kraj.strip()
    if len(od) == 10:  # samo datum -> od pocetka dana
        od += " 00:00:00"
    if len(do) == 10:  # samo datum -> do kraja dana
        do += " 23:59:59"

    upit = (
        f"SELECT Datum || ' ' || Vrijeme AS ts, {kolona} "
        "FROM Mjerenja "
        "WHERE (Datum || ' ' || Vrijeme) BETWEEN ? AND ? "
        "ORDER BY ts"
    )
    try:
        with db_brava:
            cur = statistika.execute(upit, (od, do))
            redovi = cur.fetchall()
    except sqlite3.Error as e:
        return json.dumps({"greska": f"Greska pri citanju baze: {e}"},
                          ensure_ascii=False)

    if not redovi:
        return json.dumps(
            {"greska": f"Nema mjerenja za '{mjerenje}' u intervalu "
                       f"{od} - {do}."},
            ensure_ascii=False,
        )

    vremena, vrijednosti = [], []
    for ts, vrijednost in redovi:
        try:
            vremena.append(datetime.strptime(ts, "%Y-%m-%d %H:%M:%S"))
        except ValueError:
            continue
        vrijednosti.append(vrijednost)

    # Nacrtaj graf.
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(vremena, vrijednosti, marker=".", linestyle="-", color="#2a7ae2")
    ax.set_title(f"{naziv} ({od} - {do})")
    ax.set_xlabel("Vrijeme")
    ax.set_ylabel(f"{naziv} [{jedinica}]")
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m %H:%M"))
    fig.autofmt_xdate()
    fig.tight_layout()

    os.makedirs(GRAFOVI_DIR, exist_ok=True)
    sigurno_ime = od.replace(":", "").replace(" ", "_") + "__" + \
        do.replace(":", "").replace(" ", "_")
    putanja = os.path.join(GRAFOVI_DIR, f"{kolona}_{sigurno_ime}.png")
    fig.savefig(putanja, dpi=120)
    plt.close(fig)

    return json.dumps(
        {"putanja": putanja, "broj_tacaka": len(vrijednosti)},
        ensure_ascii=False,
    )


def statistika_unesi_rad_pumpe(vrijeme):
    with open("DEBUG.txt", "a") as file:
        file.write("statistika_unesi_rad_pumpe-statistika_tools.py-")
    date_part, time_part =datetime.now().strftime('%Y-%m-%d %H:%M:%S').split(' ')
    try:
        with open("DEBUG.txt", "a") as file:
            file.write("insert_pump_work-")
        insert_pump_work(statistika, date_part, time_part, vrijeme)
        with open("DEBUG.txt", "a") as file:
            file.write("OK?-")
    except sqlite3.Error as e:
        return json.dumps({"greska": f"Greska pri unosu u bazu: {e}"},
                          ensure_ascii=False)
    return ""