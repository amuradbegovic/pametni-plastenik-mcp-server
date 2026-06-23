import json
import time

from globals import mcp, mqtt_client, posljednje_poruke, brava


@mcp.tool()
def tasmota_status_releja(uredjaj: str, relej: int) -> str:
    """Dobij status releja na Tasmota uredjaju

    Args:
        uredjaj: Ime Tasmota uredjaja (npr. 'lampa1', 'ventilator').
        relej: Redni broj releja povezanog na uredjaj (npr. 1, 2, 3).
    """
    stat_topic = f"stat/{uredjaj}/RESULT"
    with brava:
        posljednje_poruke.pop(stat_topic, None)

    mqtt_client.publish(f"cmnd/{uredjaj}/POWER{relej}", "")

    for _ in range(30):
        time.sleep(0.1)
        with brava:
            zapis = posljednje_poruke.get(stat_topic)
        if zapis is not None:
            return zapis["payload"]

    return "Nije bilo moguce dobiti status releja (timeout)."

@mcp.tool()
def tasmota_upali_relej(uredjaj: str, relej: int) -> str:
    """Upali relej na Tasmota uredjaju (relej/svjetlo).

    Args:
        uredjaj: Ime Tasmota uredjaja (npr. 'lampa1', 'ventilator').
        relej: Redni broj releja povezanog na uredjaj (npr. 1, 2, 3).
    """
    topic = f"cmnd/{uredjaj}/POWER{relej}"
    mqtt_client.publish(topic, "ON")
    return f"Poslana komanda UPALI uredjaju '{uredjaj}' (topic: {topic})"


@mcp.tool()
def tasmota_ugasi_relej(uredjaj: str, relej: int) -> str:
    """Ugasi relej na Tasmota uredjaju (relej/svjetlo).

    Args:
        uredjaj: Ime Tasmota uredjaja (npr. 'lampa1', 'ventilator').
        relej: Redni broj releja povezanog na uredjaj (npr. 1, 2, 3).
    """
    topic = f"cmnd/{uredjaj}/POWER{relej}"
    mqtt_client.publish(topic, "OFF")
    return f"Poslana komanda UGASI uredjaju '{uredjaj}' (topic: {topic})"


@mcp.tool()
def tasmota_citaj_senzor(uredjaj: str) -> str:
    """Procitaj svjeze podatke (senzor) sa Tasmota uredjaja.

    Salje komandu 'Status 10' uredjaju i ceka odgovor sa svjezim
    ocitanjima senzora. Ako uredjaj ne odgovori, vraca obavjestenje
    da podaci nisu dostupni (timeout).

    Args:
        uredjaj: Ime Tasmota uredjaja (npr. 'senzor_dnevni_boravak').
    """
    stat_topic = f"stat/{uredjaj}/STATUS10"
    with brava:
        posljednje_poruke.pop(stat_topic, None)

    mqtt_client.publish(f"cmnd/{uredjaj}/Status", "10")

    zapis = None
    for _ in range(30):
        time.sleep(0.1)
        with brava:
            zapis = posljednje_poruke.get(stat_topic)
        if zapis is not None:
            break

    if zapis is None:
        return f"Nije bilo moguce dobiti svjeze podatke za '{uredjaj}' (timeout)."

    payload = zapis["payload"]

    # Pokusaj parsirati JSON i pretvoriti sirovu vrijednost vlaznosti zemlje
    # (ANALOG.A2) u procente prije nego sto se podaci vrate agentu.
    # Odgovor na 'Status 10' sadrzi senzore unutar kljuca 'StatusSNS'.
    try:
        podaci = json.loads(payload)
        senzori = podaci.get("StatusSNS", podaci)
        a2 = senzori.get("ANALOG", {}).get("A2")
        # Uredjaj sada sam ocitava svjetlost (ANALOG.Illuminance1) kako treba,
        # pa pretvaranje sirove LDR vrijednosti u lux vise nije potrebno.
        if a2 is not None and a2 > 0:
            zemljap = 100 * (4000 - a2) / 2600
            senzori["ANALOG"]["A2"] = round(zemljap, 2)
            payload = json.dumps(podaci)
    except (json.JSONDecodeError, TypeError, ValueError):
        # Ako payload nije ocekivani JSON, vrati ga nepromijenjen.
        pass

    return f"Svjezi podaci ({stat_topic}): {payload}"
