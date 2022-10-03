import asyncio
import time
import json
import socket
import sys
import logging
from datetime import datetime
from gmqtt import Client as MQTTClient

logger = logging.getLogger(__name__)
OFI_TOPIC = "+/ofi/#"
REFRESH_TOPIC = "homeassistant/requests/ofi/refresh"
hostname = socket.gethostname()


# STOP = asyncio.Event()
class MQTT_Hassio():

    def __init__(self, broker_host, port, user, password, mqtt_ssl, ofi_serial):
        self.broker_host = broker_host
        self.port = port
        self.user = user
        self.password = password
        self.ssl = mqtt_ssl
        self.mqtt_client = None
        self.ofi_serial = ofi_serial

    async def connect(self):

        try:
            logger.info(
                '""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""')
            logger.info('Attempting MQTT connection...')
            logger.info('MQTT host : %s', self.broker_host)
            logger.info('MQTT user : %s', self.user)
            adress = hostname + str(datetime.fromtimestamp(time.time()))
            # logger.info(adress)

            client = MQTTClient(adress)
            # logger.info(client)

            client.on_connect = self.on_connect
            client.on_message = self.on_message
            client.on_disconnect = self.on_disconnect

            client.set_auth_credentials(self.user, self.password)
            await client.connect(self.broker_host, self.port, self.ssl, 180)

            self.mqtt_client = client
            return self.mqtt_client

        except Exception as e:
            logger.info("MQTT connection Error : %s", e)
            logger.info('MQTT error, restarting in 8s...')
            await asyncio.sleep(8)
            await self.connect()

    def on_connect(self, client, flags, rc, properties):
        logger.info("##################################")
        try:
            logger.info("Subscribing to : %s", OFI_TOPIC)
            # client.subscribe('homeassistant/#', qos=0)
            client.subscribe('homeassistant/status', qos=0)
            client.subscribe(OFI_TOPIC, qos=0)
        except Exception as e:
            logger.info("Error on connect : %s", e)

    async def on_message(self, client, topic, payload, qos, properties):
        logger.debug('Incoming MQTT message : %s %s', topic, payload)
        if ('update' in str(topic)):
            #        if "update" in topic:
            logger.info('Incoming MQTT update request : ', topic, payload)
        elif ('kill' in str(topic)):
            #        if "update" in topic:
            logger.info('Incoming MQTT kill request : %s %s', topic, payload)
            logger.info('Exiting...')
            sys.exit()
        elif (topic == REFRESH_TOPIC):
            logger.info(
                'Incoming MQTT refresh request : %s %s',
                topic,
                payload)
        elif (topic == "homeassistant/status" and payload.decode() == 'online'):
            logger.info('Incoming MQTT status online')
        else:
            pass
            # logger.debug(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
            # logger.debug('MQTT incoming : ', topic, payload.decode())

    def on_disconnect(self, client, packet, exc=None):
        logger.info('MQTT Disconnected !')
        logger.info("##################################")
        # self.connect()