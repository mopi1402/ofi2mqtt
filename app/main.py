#!/usr/bin/env python3
import asyncio
import time
from datetime import datetime
import os
import sys
import json
import socket
import websockets
from logger import logger
import logging

# import uvloop

from mqtt_client import MQTT_Hassio
from ofi_client import OFI_Client

logger = logging.getLogger(__name__)

ofi_config_topic = "homeassistant/sensor/ofi/{}/config"
sensor_json_attributes_topic = "sensor/ofi/{}/state"


# HASSIO ADDON
logger.info("~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
logger.info("~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
logger.info("~~~~~~~~~~~~~~~~~~~~~~~~~~~~")

logger.info("STARTING OFI2MQTT")

logger.info("Detecting environnement......")

# uvloop.install()
# logger.info('uvloop init OK')
# DEFAULT VALUES


OFI_SERIAL = ""
MQTT_HOST = "localhost"
MQTT_PORT = 1883
MQTT_USER = ""
MQTT_PASSWORD = ""
MQTT_SSL = False
REFRESH_INTERVAL = 60

data_options_path = "/data/options.json"

try:
    with open(data_options_path) as f:
        logger.info(
            f"{data_options_path} detected ! Hassio Addons Environnement : parsing options.json...."
        )
        try:
            data = json.load(f)
            logger.debug(data)

            # CREDENTIALS OFI
            if data["OFI_SERIAL"] != "":
                OFI_SERIAL = data["OFI_SERIAL"]  # OFI Serial
            else:
                logger.error("No OFI serial set")
                exit()

            # CREDENTIALS MQTT
            if data["MQTT_HOST"] != "":
                MQTT_HOST = data["MQTT_HOST"]

            if data["MQTT_USER"] != "":
                MQTT_USER = data["MQTT_USER"]

            if data["MQTT_PASSWORD"] != "":
                MQTT_PASSWORD = data["MQTT_PASSWORD"]

            if data["MQTT_PORT"] != 1883:
                MQTT_PORT = data["MQTT_PORT"]

            if (data["MQTT_SSL"] == "true") or (data["MQTT_SSL"]):
                MQTT_SSL = True

        except Exception as e:
            logger.error("Parsing error %s", e)

except FileNotFoundError:
    logger.info(
        f"No {data_options_path}, seems we are not in hassio addon mode.")
    # CREDENTIALS OFI
    OFI_SERIAL = os.getenv("OFI_SERIAL") # OFI Serial
    
    # CREDENTIALS MQTT
    MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
    MQTT_USER = os.getenv("MQTT_USER", "")
    MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")
    # 1883 #1884 for websocket without SSL
    MQTT_PORT = os.getenv("MQTT_PORT", 1883)
    MQTT_SSL = os.getenv("MQTT_SSL", False)

hassio = MQTT_Hassio(
    broker_host=MQTT_HOST,
    port=MQTT_PORT,
    user=MQTT_USER,
    password=MQTT_PASSWORD,
    mqtt_ssl=MQTT_SSL,
    ofi_serial=OFI_SERIAL,
)

ofi_client = OFI_Client(ofi_serial=OFI_SERIAL)


def loop_task():
    logger.info("Starting main loop_task")

    loop = asyncio.get_event_loop()
    loop.run_until_complete(hassio.connect())

    # retrieve ofi configuration without any historical data
    ofi = ofi_client.getConfig()

    # https://www.home-assistant.io/integrations/sensor.mqtt/
    ofi_id = ofi['ofiNetworkId']
    device = {}
    device['manufacturer'] = 'CCEI'
    device['model'] = 'OFI'
    device['name'] = ofi['bluetoothId']
    device['identifiers'] = ofi_id
    device['sw_version'] = ofi['softwareVersion']

    config = {}
    config['name'] = ofi['bluetoothId']
    config['unique_id'] = ofi_id
    config['icon'] = 'mdi:pool'
    config['available'] = False
    config['state_class'] = 'measurement'
    config['device'] = device
    config['state_topic'] = sensor_json_attributes_topic.format(ofi_id).lower()

    logger.debug( json.dumps(config))

    hassio.mqtt_client.publish((ofi_config_topic.format(ofi_id)).lower(), json.dumps(config), qos=0, retain=True)

    loop.run_until_complete(listen_ofi_forever(ofi_client, ofi, device))


async def listen_ofi_forever(ofi_client, ofi_config, parent_device):
    """
    Connect, then receive all server messages and pipe them to the handler, and reconnects if needed
    """

    timestamp = ofi_config['lastUpdate']
    ofi_id = ofi_config['ofiNetworkId']

    while True:
        state = ofi_client.update( timestamp )

        hassio.mqtt_client.publish((sensor_json_attributes_topic.format(ofi_id)).lower(), {}, qos=0, retain=True)

        ofi_device = ofi_config['bluetoothId'].lower()

        battery_index = state['ofi']['battery']

        if battery_index == 0:
            battery_icon = 'mdi:battery-alert-variant-outline'
            battery_level = '< 5%'
        elif battery_index == 1:
            battery_icon = 'mdi:battery-low'
            battery_level = '< 30%'
        elif battery_index == 2:
            battery_icon = 'mdi:battery-medium'
            battery_level = '30-60 %'
        else:
            battery_icon = 'mdi:battery-high'
            battery_level = '60-100 %'

        entities_config = [
            {
                'type': 'battery',
                'icon': battery_icon,
                'state': battery_level,
                'name' : 'Batterie'
            },
            {
                'type': 'temperature',
                'unit_of_measurement' : '°C',
                'icon': 'mdi:pool-thermometer',
                'state_class': 'measurement',
                'state': state['values']['temperature']['value'],
                'name' : state['values']['temperature']['label'],
            },
            {
                'type': 'ph',
                'state': state['values']['ph']['value'],
                'name' : state['values']['ph']['label'],
            },
            {
                'type': 'redox',
                'unit_id': 'unit',
                'state': state['values']['redox']['value'],
                'name' : state['values']['redox']['label'],
            },
            {
                'type': 'conductivity',
                'unit_id': 'unit',
                'state': state['values']['conductivity']['value'],
                'name' : state['values']['conductivity']['label'],
            },
            {
                'type': 'salinity',
                'unit_id': 'unit',
                'state': state['values']['salinity']['value'],
                'name' : state['values']['salinity']['label'],
            },
        ]

        for entity_config in entities_config:
            entity_sub_id = entity_config['type']
            unique_id = f'{ofi_device}_{entity_sub_id}'.lower()

            entity = {}
            entity['friendly_name'] = entity_config['name']
            entity['name'] = unique_id
            entity['unique_id'] = unique_id
            if 'icon' in entity_config:
                entity['icon'] = entity_config['icon']
            if 'device_class' in entity_config:
                entity['device_class'] = entity_config['type']
            if 'unit_of_measurement' in entity_config:
                entity['unit_of_measurement'] = entity_config['unit_of_measurement']
            #elif 'unit_id' in entity_config:
            #    entity['unit_of_measurement'] = state['values'][entity_type][entity_config['unit_id']]
            if 'state_class' in entity_config:
                entity['state_class'] = entity_config['state_class']
            entity['device'] = parent_device
            entity['state_topic'] = sensor_json_attributes_topic.format(unique_id).lower()
            state_value = entity_config['state']

            
            hassio.mqtt_client.publish(ofi_config_topic.format(unique_id).lower(), json.dumps(entity), qos=0, retain=True)
            hassio.mqtt_client.publish(entity['state_topic'], state_value, qos=0, retain=True)


            logger.debug( '[published] ' + ofi_config_topic.format(unique_id).lower() )

        
        #timestamp = state['ofi']['lastUpdate']
       
        #    'lastCalibrationTimestamp': 1617287530871}

        time.sleep( REFRESH_INTERVAL )


if __name__ == "__main__":
    loop_task()
