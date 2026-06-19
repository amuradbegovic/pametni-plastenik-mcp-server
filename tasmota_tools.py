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
    """Procitaj posljednju telemetriju (senzor) sa Tasmota uredjaja.

    Vraca posljednju primljenu SENSOR poruku. Ako uredjaj jos nije
    objavio podatke, vraca obavjestenje da podaci nisu dostupni.

    Args:
        uredjaj: Ime Tasmota uredjaja (npr. 'senzor_dnevni_boravak').
    """
    topic = f"tele/{uredjaj}/SENSOR"
    with brava:
        zapis = posljednje_poruke.get(topic)
    if zapis is None:
        return f"Nema podataka za '{uredjaj}'. Uredjaj jos nije objavio telemetriju."

    payload = zapis["payload"]

    # Pokusaj parsirati JSON i pretvoriti sirovu LDR vrijednost (ANALOG.A3)
    # u osvjetljenje (lux) prije nego sto se podaci vrate agentu.
    try:
        podaci = json.loads(payload)
        a3 = podaci.get("ANALOG", {}).get("A3")
        if a3 is not None and a3 > 0:
            lux = 1.25 * 1e7 * (a3 ** -1.4059)
            podaci["ANALOG"]["A3"] = round(lux, 2)
            payload = json.dumps(podaci)
    except (json.JSONDecodeError, TypeError, ValueError):
        # Ako payload nije ocekivani JSON, vrati ga nepromijenjen.
        pass

    return f"Posljednji podaci ({topic}): {payload}"
