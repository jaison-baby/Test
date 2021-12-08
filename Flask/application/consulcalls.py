import requests
from flask import Flask
from exceptions import ConcsulError

class ConsulConnection(object):
    """
    class that handles consul methods. Consul is used as service discovery endpoint for
    micro services. https://walkingtree.tech/service-discovery-microservices/
    https://sreeninet.wordpress.com/2016/04/17/service-discovery-with-consul/
    """
    def __init__(self, app: Flask):
        self.app = app
        self.consul_host = getattr(app, 'consul_host', 'consul:8500')
        self.consul_health_api = getattr(app, 'consul_health_api', '/v1/health/service/')
        self.consul_catalog_api = getattr(app, 'consul_catalog_api', '/v1/catalog/service/')

    def disover_with_health(self, service: str, filter: str = 'passing'):
        """
        using consul health api to get the healthy service endpoints
        https://www.consul.io/api-docs/health
        :param service:  name of service whose endpoint is requesting
        :param filter:   parameter to filter services, default is health check passing
        :return: service endpoint
        """
        consul_url = 'http://{}{}{}'.format(self.consul_host, self.consul_health_api, service)
        params = filter
        try:
            res = requests.get(url = consul_url, params = params)
            services = res.json()
            if services:
                address = self.__get_address(services, 0)
                port = self.__get_port(services, 0)
                service_endpoint = 'http://{}:{}'.format(address, port)
                return service_endpoint
            else:
                return None
        except Exception as e:
            raise ConcsulError('Got consul exception', original_exception=e)

    @staticmethod
    def __get_address(services, idx):
        if services[idx]['Service']['Address']:
            return services[idx]['Service']['Address']
        else:
            return services[idx]['Node']['Address']

    @staticmethod
    def __get_port(services, idx):
        return services[idx]['Service']['Port']
