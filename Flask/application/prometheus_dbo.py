from flask import Flask,current_app
import logging as log
from exceptions import PrometheusError
from prometheus_api_client import PrometheusConnect
from config import config
import time
from utils import EventLogger

configData = config()

class PrometheusAPI:
	"""docstring for PrometheusAPI"""
	def __init__(self):
		log.basicConfig(level=log.DEBUG, format='%(asctime)s %(levelname)s:\n%(message)s\n')
		self.prometheus_url = configData.PROMETHEUS_URL
		self.prometheus_avg_interval = configData.PROMETHEUS_AVERAGE_INTERVAL
		self.prometheus_instant_interval = configData.PROMETHEUS_INSTANT_INTERVAL
		self.prometheus_key = configData.PROMETHEUS_KEY
		self.prom = PrometheusConnect(url=self.prometheus_url, disable_ssl=True)
		#sample id for logging only 
		self.event_id = "dbf7f453-e4b0-4297-ae22-7af87d4e2655c4"
		self.event = EventLogger(self.event_id, 'WolbfAPI', current_app)

	def dictMaker(self,metricdata,key,parameterName):
		""" Dictinary maker function for prometheus """
		dictMetric = {}
		for metric in metricdata:
			if metric['metric'][key]:
				mykey = metric['metric'][key]
				dictMetric[mykey] = {
					"timestamp" : metric["value"][0],
					parameterName: metric["value"][1]
				}
			
		return dictMetric

	def dictMaker3(self,metricdata,key):
		""" Dictinary maker function for prometheus """
		no_of_instances=0
		dictMetric = {}
		metricsum=0.0
		if metricdata:
			for metric in metricdata:
				if metric['metric'][key]:
					metricsum= metricsum + float(metric["value"][1])
					no_of_instances=no_of_instances+1
			dictMetric["sum"] = metricsum	
			dictMetric["no_of_instances"] = no_of_instances		
		return dictMetric

	def getMetrics(self):
		""" Reads the Metric Data from prometheus. This will return the per instance total stream count which is the sum of hls and rtmp streams  """
		try:
			metric_data = self.prom.custom_query(query="sum by ("+self.prometheus_key+") (avg_over_time(wowza_connection_count{"+self.prometheus_key+"!~''}["+self.prometheus_instant_interval+"]))")
			modified_data = self.dictMaker(metric_data,self.prometheus_key,"connections")
			return modified_data
		except Exception as e:
			self.event.log(e)
			return None

	def getInstanceMetricSum(self,instance_ids):
		""" This returns the total average stream across all instances"""
		try:
			metric_data = self.prom.custom_query(query="sum by ("+self.prometheus_key+") (avg_over_time(wowza_connection_count{"+self.prometheus_key+"=~'"+instance_ids+"'}["+self.prometheus_avg_interval+"]))")
			if metric_data:
				modified_data = self.dictMaker3(metric_data,self.prometheus_key)
				return modified_data
			else:
				return None
		except Exception as e:
			self.event.log(e)
			return None

	def getInstantLoadAvg(self):
		# metric 'node_load1' gives the 1 minute average of load
		try:
			metric_data = self.prom.custom_query(query="sum by("+self.prometheus_key+")(avg_over_time(node_load1{"+self.prometheus_key+"!~''}["+self.prometheus_instant_interval+"]))")
			modified_data = self.dictMaker(metric_data,self.prometheus_key,"load_avg")
			return modified_data
		except Exception as e:
			self.event.log(e)
			return None

	def getAverageSumOfLoadAvg(self,instance_ids):
		""" This returns the total average load of all instances"""
		# metric 'node_load5' gives the 5 minute average of load
		# changed to node_load1 as per client request
		try:
			metric_data = self.prom.custom_query(query="sum by ("+self.prometheus_key+")(avg_over_time(node_load1{"+self.prometheus_key+"=~'"+instance_ids+"'}["+self.prometheus_avg_interval+"]))")
			if metric_data:
				modified_data = self.dictMaker3(metric_data,self.prometheus_key)
				return modified_data
			else:
				return None
		
		except Exception as e:
			self.event.log(e)
			return None

	def bootstrap_check(self, instance_id, timeout):
		"""" This will do the bootstrap check on the given instance to make sure that prometheus is able to scrape the metrics from this instance"""
		timer = 0
		check_quey = f'sum by ({self.prometheus_key}) (avg_over_time(wowza_connection_count{{{self.prometheus_key}="{instance_id}"}}[{self.prometheus_instant_interval}]))'

		while timer < timeout:
			res = self.prom.custom_query(query=check_quey)

			try:
				if (res[0]['metric']['instance_id'] == instance_id and float(res[0]['value'][1]) >= 0):
					return True
				else:
					return False
			except IndexError as e:
				pass
			except Exception as e:
				raise PrometheusError("Error in bootstrap check", original_exception=e)

			timer += 20
			time.sleep(20)
		return False


