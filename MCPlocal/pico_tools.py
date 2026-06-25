import json
import time

from globals import TIM, mcp, mqtt_client, posljednje_poruke, brava


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
