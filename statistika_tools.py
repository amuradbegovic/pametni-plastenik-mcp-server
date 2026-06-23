import json
import sqlite3

from globals import mcp, statistika, db_brava


@mcp.tool()
def statistika_sql_upit(sql: str) -> str:
    """Izvrsi SQL SELECT upit nad bazom mjerenja iz plastenika.

    Koristi ovaj alat za odgovaranje na pitanja o izmjerenim podacima,
    npr. prosjecna temperatura u nekom periodu, maksimalna vlaznost zraka,
    broj mjerenja u danu i slicno. Sam sastavi odgovarajuci SELECT upit
    na osnovu opisanih kolona, pa rezultat protumaci korisniku.

    Baza ima jednu tabelu 'Mjerenja' sa kolonama:
        ID               INTEGER  - redni broj zapisa
        Datum            TEXT     - datum mjerenja, format 'YYYY-MM-DD'
        Vrijeme          TEXT     - vrijeme mjerenja, format 'HH:MM:SS'
        VlaznostZemlje   REAL     - vlaznost zemlje u procentima (%)
        CO2              REAL     - koncentracija CO2
        Svjetlost        REAL     - osvjetljenje u luksima (lux)
        TemperaturaZraka REAL     - temperatura zraka (stepeni C)
        VlaznostZraka    REAL     - vlaznost zraka (%)
        TackaRosista     REAL     - tacka rosista (stepeni C)

    Dozvoljeni su samo SELECT (ili WITH) upiti; svaki drugi upit se odbija.
    Rezultat se vraca kao JSON sa kljucevima 'kolone' i 'redovi'.

    Args:
        sql: SQL SELECT naredba. Primjer za prosjecnu temperaturu u periodu:
             "SELECT AVG(TemperaturaZraka) AS prosjek FROM Mjerenja
              WHERE Datum = '2026-06-23'
                AND Vrijeme BETWEEN '17:00:00' AND '18:00:00'"
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
