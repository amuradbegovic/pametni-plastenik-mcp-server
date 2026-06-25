import json
import time
import sqlite3

from globals import (
    TIM, mcp, mqtt_client, posljednje_poruke, brava,
    taster_cond, taster_brojac, statistika, db_brava,
)

# Kursor: koliko pritisaka tastera je agent vec "potrosio". None dok prvi poziv
# ne postavi baznu vrijednost (da se ignorisu pritisci prije pocetka nadzora).
# Lokalno stanje alata, cuvamo ga pod taster_cond bravom kao i taster_brojac.
_taster_kursor = [None]


def _zadnje_mjerenje_poruka() -> str:
    """Procitaj posljednje mjerenje direktno iz baze i formatiraj poruku.

    Radi se direktan SQL upit nad postojecom 'statistika' konekcijom (ista
    infrastruktura kao statistika_sql_upit) da agent ne mora zvati zaseban
    MCP alat - time se izbjegava dodatni LLM tool-call i ubrzava odgovor.
    """
    try:
        with db_brava:
            cur = statistika.execute(
                "SELECT Datum, Vrijeme, VlaznostZemlje, CO2, Svjetlost, "
                "TemperaturaZraka, VlaznostZraka, TackaRosista "
                "FROM Mjerenja ORDER BY ID DESC LIMIT 1"
            )
            red = cur.fetchone()
    except sqlite3.Error as e:
        return f"Taster pritisnut, ali greska pri citanju mjerenja iz baze: {e}"

    if red is None:
        return "Taster pritisnut, ali u bazi jos nema nijednog mjerenja."

    datum, vrijeme, vl_zemlje, co2, svjetlost, temp, vl_zraka, rosa = red
    return (
        f"Taster pritisnut. Posljednje mjerenje ({datum} {vrijeme}): "
        f"vlaznost zemlje {vl_zemlje}%, CO2 {co2} ppm, svjetlost {svjetlost} lux, "
        f"temperatura zraka {temp} C, vlaznost zraka {vl_zraka}%, "
        f"tacka rosista {rosa} C."
    )


@mcp.tool()
def pico_posalji_naredbu(uredjaj: str, naredba_json: str) -> str:
    """Posalji JSON naredbu custom picoETF uredjaju.

    Args:
        uredjaj: Ime vaseg picoETF uredjaja (npr. 'pico_igra').
        naredba_json: JSON string sa naredbom, npr. '{"akcija":"upali_led"}'.
    """
    try:
        json.loads(naredba_json)
    except json.JSONDecodeError as e:
        return f"GRESKA: naredba_json nije validan JSON: {e}"

    topic = f"etf/us/2026/{TIM}/{uredjaj}/cmd"
    mqtt_client.publish(topic, naredba_json)
    return f"Poslana naredba uredjaju '{uredjaj}' (topic: {topic}): {naredba_json}"


@mcp.tool()
def pico_citaj_podatke(uredjaj: str) -> str:
    """Procitaj posljednje JSON podatke sa custom picoETF uredjaja.

    Args:
        uredjaj: Ime vaseg picoETF uredjaja (npr. 'pico_senzor').
    """
    topic = f"etf/us/2026/{TIM}/{uredjaj}/data"
    with brava:
        zapis = posljednje_poruke.get(topic)
    if zapis is None:
        return f"Nema podataka za '{uredjaj}'. Uredjaj jos nije objavio podatke."
    return f"Posljednji podaci ({topic}): {zapis['payload']}"


@mcp.tool()
def pico_cekaj_taster(timeout_s: int = 55) -> str:
    """Cekaj (dugo-poll) na pritisak treceg tastera na picoETF uredjaju.

    Blokira do timeout_s sekundi cekajuci da treci taster bude pritisnut
    (uredjaj objavi "3" na topic etf/us/2026/plastenik/picoetf/taster).
    Cim pritisak stigne, alat sam procita posljednje mjerenje iz baze i vrati
    gotovu poruku sa ocitanjima senzora (pocinje sa "Taster pritisnut."), pa
    agent tu poruku samo proslijedi. Ako u zadatom periodu nema pritiska,
    vraca "TIMEOUT" pa ga agent moze ponovo pozvati.

    Pritisci koji se dese dok agent obradjuje prethodni (izmedju dva poziva)
    se ne gube - sljedeci poziv se odmah vraca jer je brojac u medjuvremenu
    porastao. Pritisci prije prvog poziva (prije pocetka nadzora) se ignorisu.

    Args:
        timeout_s: Koliko sekundi maksimalno cekati (preporuceno 30-55).
    """
    if timeout_s is None or timeout_s <= 0:
        timeout_s = 55
    with taster_cond:
        # Prvi poziv: ignorisi sve sto se desilo prije pocetka nadzora.
        if _taster_kursor[0] is None:
            _taster_kursor[0] = taster_brojac[0]
        start = _taster_kursor[0]
        rok = time.monotonic() + timeout_s
        while taster_brojac[0] == start:
            preostalo = rok - time.monotonic()
            if preostalo <= 0:
                return "TIMEOUT: treci taster nije pritisnut u zadatom periodu."
            taster_cond.wait(preostalo)
        # Potrosi sve pritiske do sada (vise pritisaka -> jedna obavijest).
        _taster_kursor[0] = taster_brojac[0]
    # Pritisak detektovan -> odmah procitaj zadnje mjerenje iz baze i vrati
    # gotovu poruku (bez dodatnog MCP tool-calla / LLM round-tripa).
    return _zadnje_mjerenje_poruka()


@mcp.tool()
def izlistaj_aktivne_uredjaje() -> str:
    """Izlistaj sve uredjaje koji su nedavno objavili poruke na brokeru.

    Korisno za 'otkrivanje' uredjaja - agent ovako vidi sta je aktivno
    u mrezi bez da unaprijed zna imena uredjaja.
    """
    with brava:
        if not posljednje_poruke:
            return "Nijedan uredjaj jos nije objavio poruke. Pricekajte ili provjerite uredjaje."
        redovi = []
        sada = time.time()
        for topic, zapis in sorted(posljednje_poruke.items()):
            starost = int(sada - zapis["vrijeme"])
            redovi.append(f"  {topic}  (prije {starost}s)")
        return "Aktivni topic-i (uredjaji):\n" + "\n".join(redovi)
