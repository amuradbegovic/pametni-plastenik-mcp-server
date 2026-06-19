# pametni-plastenik-mcp-server

## Organizacija koda 
`globals.py` - varijable i funkcije koje su potrebne svim modulima

`main.py` - entry point servera

`pico_tools.py` - MCP toolovi za Raspberry Pi Pico

`tasmota_tools.py` - MCP toolovi za ESP32 sa Tasmota firmware-om

## Instalacija

`python -m venv venv`

`source ./venv/bin/activate`

`pip install -r requirements.txt # nije potrebno u containeru u laboratoriji`

`git clone https://github.com/amuradbegovic/pametni-plastenik-mcp-server`

`hermes mcp add pametni-plastenik --command "/put/do/pametni-plastenik-mcp-server/venv/bin/python" --args "/put/do/pametni-plastenik-mcp-server/main.py"`
