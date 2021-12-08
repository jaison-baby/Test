from celery import shared_task
from datetime import datetime
import uuid 
import secrets
import string
import os, sys
from dbo import WolbfAPI
from prometheus_dbo import PrometheusAPI
from config import config
from inspector_utils import InspectorScaler
from flask import current_app
from utils import EventLogger


configData = config()

@shared_task
def connectionRequest():
	"""  Average Wise Approach to compute the autoscaling decison  """
	wolbf_obj = WolbfAPI()
	event_id = wolbf_obj.generate_uuid()
	event = EventLogger(event_id, 'onNewRequest', current_app)
	event_info = wolbf_obj.getEventByStatus('INPROGRESS')
	if event_info:
		scaler = InspectorScaler(current_app,event_info['event_id'])
		scaler.checkForEventTimeout(event_info)				
	else:
		# no events running at the moment
		scaler = InspectorScaler(current_app,event_id)
		pg_active_instances,instance_ids = scaler.getPostgressInstanceIDs(["ACTIVE"])

		if pg_active_instances < configData.MIN_NO_OF_INSTANCES:
			# scale up the minimum desired instances if its not available
			scaler = InspectorScaler(current_app,event_id)
			scaler.checkEipAndDoScaleUp()
		else:
			# minimum instances satisfied
			avg_of_active_instances = 0
			sum_of_active_instances=0
			if instance_ids:
				prom_active_instances,sum_of_active_instances=scaler.getTheSumOfInstances(instance_ids,"connection")
				if prom_active_instances:
					if sum_of_active_instances:
						avg_of_active_instances = sum_of_active_instances/prom_active_instances
						event.log("avg_of_active_instances active:{}".format(avg_of_active_instances))
						if avg_of_active_instances:
							if avg_of_active_instances < configData.AUTOSCALING_THRESHOLD_COUNT:
								# scaledown logic
								# check the load before proceeding
								load_avg = scaler.checkLoadAvgOfInstances(instance_ids,False)
								if load_avg == True:
									scaler.checkForScaledown()
									
							else:
								#scaleup logic
								event.log("Scale Up Logic")
								event.log("prom_active_instances :{}".format(prom_active_instances))
								scaler = InspectorScaler(current_app,event_id)
								percentage = scaler.getDifferencePercentage(avg_of_active_instances,"scaleup") 
								event.log("percentage:{}".format(percentage))
								if percentage > configData.PERCENTAGE_THRESHOLD:
									scaler.checkForScaleup(prom_active_instances)
					else:
						scaler = InspectorScaler(current_app,event_id)
						scaler.checkForScaledown()
						
	return {"data":"Done"}