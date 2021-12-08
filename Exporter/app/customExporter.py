import time
import re
from random import randrange

from prometheus_client.core import GaugeMetricFamily, REGISTRY, CounterMetricFamily
from prometheus_client import start_http_server
import requests
import xml.etree.ElementTree as ET
import json
from werkzeug.middleware.dispatcher import DispatcherMiddleware
import os

wowza_endpoint = os.environ.get('WOWZA_ENDPOINT', "localhost")
wowza_application = os.environ.get('WOWZA_APPLICATION', "live1")


class CustomCollector(object):
    def __init__(self):
        pass

    def collect(self):
        hls_count = 0
        rtmp_count = 0
        try:
            url="http://"+wowza_endpoint+":8087/v2/servers/_defaultServer_/vhosts/_defaultVHost_/applications/"+wowza_application+"/monitoring/current"
            headers = {
            'Content-type': 'application/json',
            'Accept':'application/json',
            'Accept-Charset': 'UTF-8'
            }
            response = requests.get(url, headers=headers)
            if response.status_code & response.status_code==200:
                resjson = response.json()
                connectionCount = resjson.get('connectionCount')
                if connectionCount:
                    rtmp_count = connectionCount.get("RTMP")
                    hls_count = connectionCount.get("CUPERTINO")
                else:
                    print("Parameter connectionCount not available")
            else:
                print("Wowza monitoring request failed- status_code:"+response.status_code+", message:"+response.text)

            services = {'hls_collector': hls_count, 'rtmp_collector': rtmp_count}
            if services:
                for service in services:
                    # wowza_connection_count  service specific Gauge metric
                    wowza_logs = GaugeMetricFamily("wowza_connection_count", 'Wowza Connection Counts',
                                                   labels=['service'])
                    service_name = service
                    count = services[service]
                    wowza_logs.add_metric([service_name], count)
                    yield wowza_logs
        except requests.exceptions.RequestException as e:
            print("Error occured. Reason: {}".format(e))
            return None


if __name__ == '__main__':
    start_http_server(5000)
    REGISTRY.register(CustomCollector())
    while True:
        time.sleep(20)
