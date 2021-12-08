import os, sys
#currentdir = os.path.dirname(os.path.realpath(__file__))
#parentdir = os.path.dirname(currentdir)
#sys.path.append(parentdir)
from flask import Flask, request, json, Response, Blueprint, jsonify, current_app
from datetime import datetime
import logging as log
from exceptions import APIError, RedisError
from config import config
import uuid 
import secrets
import requests
import string
from dbo import WolbfAPI
from prometheus_dbo import PrometheusAPI
from inspector_utils import InspectorScaler
from models import tbl_eip_mappings,tbl_events,tbl_instance
from utils import EventLogger


configData = config()


inspector_blueprint = Blueprint('inspector', __name__)

@inspector_blueprint.route('/streaming_server',methods=['GET'])
def streaming_server():
	""" Gocoder api to return the least  loaded wowza instance """
	wolbf_obj = WolbfAPI()
	# pg_response = obj.getInstancesByStatus("ACTIVE")
	# no_of_instances = len(pg_response)

	response,status_code = wolbf_obj.getAllEIP()
	if status_code & status_code == 200:
		return {"status_code":status_code,"data":response}
	else:
		return {"status_code":status_code,"detail":response}



# ---------------------------------
# Sample Codes for checking purposes
# ---------------------------------

@inspector_blueprint.route('/getMetrics',methods=['GET'])
def metrics():
	""" Sample code to fetch the metrics from prometheus """
	prom_obj=PrometheusAPI()
	prom_response = prom_obj.getInstantLoadAvg() 
	no_of_metricsdata = len(prom_response)
	
	return {"data":prom_response} 

@inspector_blueprint.route('/getInstances',methods=['GET'])
def instances():
	""" Sample code to fetch the instances from tbl_instance """
	obj = WolbfAPI()
	a = request.args.get("a")
	b = request.args.get("b")
	if a and b:
		status=[a,b]
	elif a and not b:
		status=[a]
	elif b and not a:
		status=[b]
	else:
		status=[]
	data = obj.getInstancesByStatus(status)
	return {"data":data} 

@inspector_blueprint.route('/removeEip',methods=['GET'])
def removeEip():
	""" Sample code to fetch the instances from tbl_instance """
	obj = WolbfAPI()
	eip = request.args.get("eip")
	event_id=""
	event_id=request.args.get("event_id")
	obj.removeInstanceFromEip({'eip':eip,'status':'DETACHED','event_id':event_id})
	return {"data":"updated"}

@inspector_blueprint.route('/deleteEip',methods=['GET'])
def deleteEip():
	""" Sample code to fetch the instances from tbl_instance """
	obj = WolbfAPI()
	eip = request.args.get("eip")
	obj.deleteEip({'eip':eip})
	return {"data":"deleted"}

@inspector_blueprint.route('/getEvents',methods=['GET'])
def getEvents():
	""" Sample Code to fetch the Events from tbl_events """
	obj = WolbfAPI()
	status = request.args.get("status")
	data = obj.getEventByStatus(status)
	return {"data":data} 

@inspector_blueprint.route('/getEip',methods=['GET'])
def getEip():
	""" Sample Code to fetch the Events from tbl_events """
	obj = WolbfAPI()
	status = ""
	status = request.args.get("status")
	data = obj.getEIPByStatus(status)
	return {"data":data} 

@inspector_blueprint.route('/deleteInstance',methods=['GET'])
def deleteInstance():
	""" Sample code to delete an instaance """
	instance_id = request.args.get("instance_id")
	obj = WolbfAPI()
	if instance_id:
		obj.delete({"instance_id":instance_id})

	return {"data":"deleted:"}

@inspector_blueprint.route('/health')
def healthcheck():
    data = {
        'status': 'healthy'
    }
    return json.dumps(data)

@inspector_blueprint.route('/getInstanceLogs',methods=['GET'])
def getInstanceLogs():
	""" Sample code to check history logs of instances """
	obj = WolbfAPI()
	instance_id = request.args.get("instance_id")
	data = obj.getInstanceLogs(instance_id)
	return {"data":data}

@inspector_blueprint.route('/update',methods=['GET'])
def update():
	""" Sample code to check history logs of instances """
	obj = WolbfAPI()
	# event_id = obj.generate_uuid()
	event_id = request.args.get("event_id")
	status = request.args.get("status")
	event_data = {"event_id":event_id,"event_status":status}
	obj.updateEventStatus(event_data)
	return {"data":"updated"}

@inspector_blueprint.route('/insertToEip',methods=['GET'])
def insertToEip():
	obj=WolbfAPI()
	eip = request.args.get("eip")
	origin_domain = request.args.get("origin_domain")
	playback_domain = request.args.get("playback_domain")
	if eip :
		data={
			"eip":eip,
			"origin_domain":origin_domain,
			"playback_domain":playback_domain,
			"status":"DETACHED"
		}
		data = obj.insert(tbl_eip_mappings,data)
		return "Data available"
	else:
		return {"data":"please pass all parameters"}


@inspector_blueprint.route('/insertToEvents',methods=['GET'])
def insertToEvents():
	obj=WolbfAPI()
	eip = request.args.get("eip")
	event_data={
	"event_id":obj.generate_uuid(),
	"start_time":datetime.now(),
	"activity":"SCALEUP",
	"activity_descriptions" : "Scaleup Requested at %s" % (datetime.now()),
	"event_status":"INPROGRESS",
	"last_updated_time":datetime.now()
	}
	obj.insert(tbl_events,event_data)

	return {"data":"success"}

@inspector_blueprint.route('/getEventLogs',methods=['GET'])
def getEventLogs():
	""" Sample code to delete an instaance """
	event_id = request.args.get("event_id")
	obj = WolbfAPI()
	data = obj.getEventLogsById(event_id)
	return {"data":data}

@inspector_blueprint.route('/protectEip',methods=['GET'])
def protectEip():
	""" Sample code to delete an instaance """
	eip = request.args.get("eip")
	obj = WolbfAPI()
	data = obj.protectEip(eip)
	return {"data":"eip protected"}

@inspector_blueprint.route('/leastNode',methods=['GET'])
def leastNode():
	""" Sample code to find leastNode  """
	status = request.args.get("status")
	obj = WolbfAPI()
	data = obj.leastConnectionInstanceFromDB([status])
	return {"data":data}

