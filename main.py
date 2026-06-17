#!/usr/bin/env python3
# =============================================================================
#  MCP server za pametni plastenik
# 
#  Red. prof. dr Samim Konjicija, Ugradbeni sistemi, 2026. godina.
#
#  Pokretanje (za testiranje, van Hermesa):
#    python3 main.py
#
#  Hermes ce ovaj server pokretati automatski kad ga registrujete kao MCP server.
# =============================================================================

import tasmota_tools  # registruje @mcp.tool() dekoratore
import pico_tools     # registruje @mcp.tool() dekoratore

from globals import mcp, mqtt_client, MQTT_HOST, MQTT_PORT

mqtt_client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
mqtt_client.loop_start()

if __name__ == "__main__":
    mcp.run()
