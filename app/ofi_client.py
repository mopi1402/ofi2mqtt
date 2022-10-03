import requests
import logging
#from datetime import datetime, timedelta

HOST = "pi2x5eehi5.execute-api.eu-west-1.amazonaws.com"
BASE_API = f"https://{HOST}/v2/ofi"
USER_AGENT = "okhttp/3.8.0"
LOCALE = "fr-FR"

logger = logging.getLogger(__name__)

class OFI_Client():

    def __init__(self, ofi_serial):
        self.ofi_serial = ofi_serial
        #last_year_date_time = datetime.now() - timedelta(days = 365)
        #self.timestamp = int(int(last_year_date_time.now().strftime("%s%f"))/1000000));

    def _getData(self, timestamp):
        logger.info('Fetch OFI data...')
        url = f'{BASE_API}?ofiNetworkId={self.ofi_serial}&locale={LOCALE}&timestamp={timestamp}'
        response = requests.get(url, headers={"Host":HOST, "User-Agent": USER_AGENT})
        if response.ok:
            return response.json()
        else: 
            logger.info( ' -> failed')
            return None
        

    def getConfig(self):
        response = self._getData(99999999999)
        logger.info( ' -> getConfig')
        return response['ofi']

    def update(self, timestamp):
        response = self._getData(timestamp)

        latestValues = response['data'][-1]

        data = {
            'ofi':{
                'lastUpdate': response['ofi']['lastUpdate'],
                'battery': response['ofi']['battery'],
                'lastCalibrationTimestamp': response['ofi']['lastCalibrationTimestamp']
            },
            'values':{
                'temperature':{
                    'label':response['pool']['variables']['temperature']['label'],
                    'unit':response['pool']['variables']['temperature']['unit'],
                    'min':response['pool']['variables']['temperature']['min'],
                    'max':response['pool']['variables']['temperature']['max'],
                    'value': latestValues['temperature']
                },
                'salinity':{
                    'label':response['pool']['variables']['salinity']['label'],
                    'unit':response['pool']['variables']['salinity']['unit'],
                    'value': latestValues['salinity']
                },
                'conductivity':{
                    'label': 'Conductivité',
                    'unit':'μS',
                    'value': latestValues['conductivity']
                },
                'redox':{
                    'label': response['pool']['variables']['redox']['label'],
                    'unit': 'mV',
                    'min':response['pool']['variables']['redox']['min'],
                    'max':response['pool']['variables']['redox']['max'],
                    'value': latestValues['redox']
                },
                'ph':{
                    'label':response['pool']['variables']['pH']['label'],
                    'min':response['pool']['variables']['pH']['min'],
                    'max':response['pool']['variables']['pH']['max'],
                    'value': latestValues['pH']
                }
            }
        }
        
        return data
        logger.info( 'update ->')
    