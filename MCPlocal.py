from lib.MCPlocal import mcp_dataset_functions, pico_tools, statistika_tools, tasmota_tools

# mcp_dataset_functions
def get_current_working_directory() -> str:
    mcp_dataset_functions.get_current_working_directory()

def compare_current_vs_optimal(
        plant_type: str,
        temperature: float,
        humidity_air: float,
        humidity_soil: float,
        co2: float,
        light: float,
    ) -> dict:
    mcp_dataset_functions.compare_current_vs_optimal(
        plant_type,
        temperature,
        humidity_air,
        humidity_soil,
        co2,
        light,
    )

def get_dataset_recommendation(
        plant_type: str,
        temperature: float,
        humidity_air: float,
        humidity_soil: float,
        co2: float,
        light: float,
    ) -> dict:
    mcp_dataset_functions.get_dataset_recommendation(
        plant_type,
        temperature,
        humidity_air,
        humidity_soil,
        co2,
        light,
    )

def get_optimal_conditions(plant_type: str) -> dict:
    mcp_dataset_functions.get_optimal_conditions(plant_type)

# pico_tools
def pico_posalji_naredbu(uredjaj: str, naredba_json: str) -> str:
    pico_tools.pico_posalji_naredbu(uredjaj, naredba_json)

def pico_citaj_podatke(uredjaj: str) -> str:
    pico_tools.pico_citaj_podatke(uredjaj)

def izlistaj_aktivne_uredjaje() -> str:
    pico_tools.izlistaj_aktivne_uredjaje()

# prepare_dataset
# nothing

# statistika_tools
def statistika_sql_upit(sql: str) -> str:
    statistika_tools.statistika_sql_upit(sql)

def statistika_graf(mjerenje: str, pocetak: str, kraj: str) -> str:
    statistika_tools.statistika_graf(mjerenje, pocetak, kraj)

def statistika_unesi_rad_pumpe(vrijeme):
    statistika_tools.statistika_unesi_rad_pumpe(vrijeme)

# tasmota_tools
def tasmota_status_releja(uredjaj: str, relej: int) -> str:
    tasmota_tools.tasmota_status_releja(uredjaj, relej)

def tasmota_upali_relej(uredjaj: str, relej: int) -> str:
    tasmota_tools.tasmota_upali_relej(uredjaj, relej)

def tasmota_ugasi_relej(uredjaj: str, relej: int) -> str:
    tasmota_tools.tasmota_ugasi_relej(uredjaj, relej)

def tasmota_upali_pumpu_ograniceno(uredjaj: str, relej: int, vrijeme: int) -> str:
    tasmota_tools.tasmota_upali_pumpu_ograniceno(uredjaj, relej, vrijeme)

def tasmota_citaj_senzor(uredjaj: str) -> str:
    tasmota_tools.tasmota_citaj_senzor(uredjaj)
