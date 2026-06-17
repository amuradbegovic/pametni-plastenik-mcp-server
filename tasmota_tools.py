from globals import mcp, mqtt_client, posljednje_poruke, brava


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
    return f"Posljednji podaci ({topic}): {zapis['payload']}"
