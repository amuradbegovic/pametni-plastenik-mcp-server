#!/usr/bin/env python3
# =============================================================================
#  MCP server za pametni plastenik
# 
#  Bazirano na:
#  primjer_mcp_server.py - Kostur MCP servera za vjezbu US 2026
#  Red. prof. dr Samim Konjicija, Ugradbeni sistemi, 2026. godina.
#
#  Pokretanje (za testiranje, van Hermesa):
#    python3 main.py
#
#  Hermes ce ovaj server pokretati automatski kad ga registrujete kao MCP server.
# =============================================================================

import tasmota_tools  # registruje @mcp.tool() dekoratore
import pico_tools     # registruje @mcp.tool() dekoratore
import mcp_dataset_functions # registruje @mcp.tool() dekoratore

from globals import mcp, mqtt_client, MQTT_HOST, MQTT_PORT

# Potrebno iz razloga što u suprotnom ne može pristupiti ostalim python modulima 
# kada se pokreće preko Hermesa.
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

mqtt_client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
mqtt_client.loop_start()

if __name__ == "__main__":
    mcp.run()
