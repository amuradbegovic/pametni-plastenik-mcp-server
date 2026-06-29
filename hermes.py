from run_agent import AIAgent
from tools.mcp_tool import discover_mcp_tools, has_registered_mcp_tools
import paho.mqtt.client as mqtt

# Isti .env koji koristi gateway (OPENAI_API_KEY itd.) — best-effort.
try:
    from dotenv import load_dotenv
    load_dotenv("/root/.hermes/.env")
except Exception:
    pass

# VAZNO: standalone skripta mora sama registrovati MCP servere iz config.yaml
# (mcp_servers.pametni-plastenik). Bez ovoga agent NEMA pristup senzorima/picoETF
# alatima pa "luta" po fajlovima umjesto da pozove prave alate. Pozvati jednom,
# prije prvog agent.chat().
_mcp = discover_mcp_tools()
print(f"MCP alati registrovani: {len(_mcp)} (ok={has_registered_mcp_tools()})")

# ---------------------------------------------------------------------------
#  Ponasanje agenta: drzi ga jednostavnim i brzim.
#  - skip_memory=True            -> nema cross-session recall ni background
#                                   "memory review" (samo-poboljsavanje).
#  - disabled_toolsets[...skills]-> uklanja skill_manage alat, sto je jedini
#                                   uslov koji pokrece background "skill review".
#    Ostali iskljuceni toolset-i (web/browser/terminal/vision/...) nisu potrebni
#    za ovaj zadatak; MCP alati (pico_*, tasmota_*, statistika_*) NISU u ovoj
#    listi pa ostaju dostupni.
#  - reasoning_config effort=low -> gpt-5.4-nano da ne "razmislja" previse.
#  - max_iterations=6            -> procitaj senzor -> (po potrebi baza) -> posalji
#                                   naredbu. Kratak zadatak, mali budget koraka.
# ---------------------------------------------------------------------------
SUSTAV = (
    "Ti si jednostavan kontroler za plastenik. Izvrsi zadatak u sto manje koraka. "
    "Nemoj razmisljati naglas, nemoj se samo-poboljsavati, nemoj kreirati niti "
    "azurirati vjestine (skills) ni memoriju. Pozovi samo neophodne alate: procitaj "
    "senzor, po potrebi pogledaj u bazu, i posalji naredbu picoETF uredjaju, pa zavrsi. "
    "Za citanje senzora koristi alat tasmota_citaj_senzor, a za paljenje boje/dioda alat "
    "pico_posalji_naredbu. Za prebacivanje (toggle) releja na Tasmota uredjaju koristi alat "
    "tasmota_prebaci_relej (a tasmota_upali_relej / tasmota_ugasi_relej za fiksno paljenje/gasenje). "
    "Ne pozivaj list_resources, list_prompts, get_optimal_conditions ni druge nepotrebne alate. "
    "Vjerovatno neces dobiti odgovor nazad pa ne cekaj na odziv sistema. Ne objasnjavaj opsirno."
)

agent = AIAgent(
    model="gpt-5.4-nano",
    quiet_mode=True,
    skip_memory=True,
    skip_context_files=True,
    max_iterations=6,
    reasoning_config={"effort": "low"},
    ephemeral_system_prompt=SUSTAV,
    disabled_toolsets=[
        "skills", "memory", "session_search", "delegation",
        "web", "browser", "browser-cdp", "terminal",
        "vision", "image_gen", "video_gen", "tts", "computer_use", "x_search",
    ],
)

# ---------------------------------------------------------------------------
#  Mapiranje ocitanja -> broj dioda (0..8), LINEARNO prema rasponu senzora.
#  Blizu minimuma = 0 dioda; blizu maksimuma = svih 8 dioda; izmedju 1..7.
#  (Vise nema "idealne vrijednosti" / udaljenosti od idealnog.)
#  Rasponi su procijenjeni iz dataset-a i tipicnih vrijednosti -> po potrebi ih
#  podesite (min -> 0 dioda, max -> 8 dioda).
# ---------------------------------------------------------------------------
#  Naredba za picoETF je TACNO ovog oblika (vrijednosti su 0 ili 1):
#    {"RED":r, "GREEN":g, "BLUE":b, "DIODE":[d1,...,d8]}
#  RED/GREEN/BLUE biraju boju, DIODE je niz od 8 dioda gdje je prvih N upaljeno (1).
#  Boje: crvena=(1,0,0) zelena=(0,1,0) plava=(0,0,1) zuta=(1,1,0) ljubicasta=(1,0,1)
#  Gdje se svaka vrijednost nalazi u odgovoru alata tasmota_citaj_senzor
#  (JSON pod kljucem StatusSNS): pomaze modelu da ne "ne nadje" ocitanje.
#    temperatura zraka -> DHT11.Temperature (C)
#    vlaznost zraka    -> DHT11.Humidity (%)
#    vlaznost zemlje   -> ANALOG.A2  (alat to vec pretvori u %)
#    nivo svjetla      -> ANALOG.Illuminance1 (lux)
#    nivo CO2          -> ANALOG.MQ2_1
def zadatak(boja, r, g, b, senzor, mn, mx, jed, polje):
    izvor = (
        f"vrijednost se nalazi u polju {polje} odgovora alata tasmota_citaj_senzor; "
        f"ako bas to polje nije dostupno, procijeni iz baze (statistika_sql_upit)."
        if polje else
        f"ovo ocitanje nije u tasmota odgovoru, pa uzmi posljednju vrijednost iz baze (statistika_sql_upit)."
    )
    return (
        f"Prikazi nivo senzora '{senzor}' u {boja} boji na picoETF uredjaju (ime 'picoetf'). "
        f"1) Procitaj '{senzor}' sa Tasmota uredjaja 'tasmota-plastenik' alatom tasmota_citaj_senzor — {izvor} "
        f"2) Izracunaj cijeli broj N (0..8) LINEARNO prema rasponu {mn}{jed} (=0) do {mx}{jed} (=8): "
        f"N = round(8 * (vrijednost - {mn}) / ({mx} - {mn})), ograniceno na 0..8. "
        f"Blizu {mn}{jed} je N=0; blizu {mx}{jed} je N=8. "
        f"3) Napravi niz DIODE od TACNO 8 vrijednosti gdje je prvih N jednako 1, ostatak 0. "
        f"4) Posalji alatom pico_posalji_naredbu (uredjaj='picoetf') TACNO ovaj JSON, bez mijenjanja strukture ni kljuceva: "
        f'{{"RED":{r}, "GREEN":{g}, "BLUE":{b}, "DIODE":[d1,d2,d3,d4,d5,d6,d7,d8]}} '
        f"gdje d1..d8 zamijenis nulama/jedinicama iz koraka 3. Zatim zavrsi."
    )

# ---------------------------------------------------------------------------
#  Prebacivanje (toggle) releja na Tasmota uredjaju 'tasmota-plastenik'.
#  Uredjaj ima dva releja: relej=1 -> POWER1, relej=2 -> POWER2.
#  Svaki pritisak prebacuje stanje: ugasen -> upaljen, upaljen -> ugasen.
#  Zadatak je trivijalan: pozovi tasmota_prebaci_relej i zavrsi (bez senzora/picoETF).
# ---------------------------------------------------------------------------
def zadatak_relej(relej, opis):
    return (
        f"Prebaci (toggle) relej broj {relej} ({opis}) na Tasmota uredjaju 'tasmota-plastenik'. "
        f"Pozovi alat tasmota_prebaci_relej sa argumentima uredjaj='tasmota-plastenik', relej={relej}, "
        f"pa zavrsi. Ne citaj senzore i ne salji nista picoETF uredjaju."
    )

# Raspored tastera: 1=crvena, 2=zelena, 3=plava, 4=zuta, 5=ljubicasta (senzor->diode),
# 6=toggle relej 1, 7=toggle relej 2.
prompts = [
    zadatak("crvenoj",    1, 0, 0, "temperatura zraka", 0,  50,  " C",   "DHT11.Temperature"),
    zadatak("zelenoj",    0, 1, 0, "vlaznost zraka",     0,  100, " %",   "DHT11.Humidity"),
    zadatak("plavoj",     0, 0, 1, "vlaznost zemlje",    0,  100, " %",   "ANALOG.A2"),
    zadatak("zutoj",      1, 1, 0, "nivo svjetla",       0,  100, " lux", "ANALOG.Illuminance1"),
    zadatak("ljubicastoj",1, 0, 1, "nivo CO2",           0,  200, " ppm", "ANALOG.MQ2_1"),
    zadatak_relej(1, "prvi relej"),
    zadatak_relej(2, "drugi relej"),
]


def on_connect(client, userdata, flags, reason_code, properties):
    #print(f"Connected with result code {reason_code}")
    client.subscribe("etf/us/2026/plastenik/picoetf/taster")

def on_message(client, userdata, msg):
    print(msg.topic+" "+str(msg.payload))
    try:
        taster = int(msg.payload)
        if 0 < taster <= len(prompts):
           response = agent.chat(prompts[taster-1])
           print(response)
           print(prompts[taster-1])
           print("Gotov prompt")
    except Exception as e:
        print(f'Error: {e}')
        pass

mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
mqttc.on_connect = on_connect
mqttc.on_message = on_message

mqttc.connect("195.130.59.221", 1883, 60)
print("Ready.")
mqttc.loop_forever()