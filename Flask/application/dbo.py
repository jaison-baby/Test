from flask import Flask, request, json, Response, Blueprint, jsonify, current_app
from datetime import datetime
import logging as log
from exceptions import APIError, RedisError
from database import db
from models import tbl_instance,tbl_events,tbl_instance_logs,tbl_event_logs,tbl_eip_mappings, tbl_mail_alerts
from prometheus_api_client import PrometheusConnect
from prometheus_api_client.utils import parse_datetime
from prometheus_client import start_http_server
from config import config
import os
import uuid 
from exceptions import DatabaseError
from utils import EventLogger

configData = config()


class WolbfAPI:
	def __init__(self):
		log.basicConfig(level=log.DEBUG, format='%(asctime)s %(levelname)s:\n%(message)s\n')
		self.event_id = self.generate_uuid()
		self.event = EventLogger(self.event_id, 'WolbfAPI', current_app)
	
	def generate_uuid(self):
		""" UUID function"""
		id = str(uuid.uuid4())
		return id

	def getInstancesByStatus(self,statusdata=[]):
		""" Read All data which are ACTIVE/DRAINING/BOOTSTRAPPING from tbl_instance """
		if statusdata:
			try:
				details=db.session.query(tbl_instance).join(tbl_eip_mappings,tbl_eip_mappings.attached_instance==tbl_instance.instance_id).with_entities(tbl_eip_mappings.origin_domain.label("origin_domain"),tbl_instance.load_avg.label("load_avg"),tbl_instance.event_id.label("event_id"),tbl_instance.status.label("status"),tbl_instance.last_updated_time.label("last_updated_time"),tbl_instance.instance_id.label("instance_id"),tbl_instance.privateip.label("privateip"),tbl_eip_mappings.eip.label("eip"),tbl_instance.active_connections.label("active_connections")).filter(tbl_instance.status.in_(statusdata)).order_by(tbl_instance.active_connections.asc()).all()
				data=list(map(lambda x:x._asdict(),details))
				return data
			except Exception as e:
				self.event.log(e)
				return []
		else:
			# when joining with tbl_eipmappings instances which are in bootstrapping status wont show up,so using left join
			try:
				details=db.session.query(tbl_instance).join(tbl_eip_mappings,tbl_eip_mappings.attached_instance==tbl_instance.instance_id,isouter=True).with_entities(tbl_eip_mappings.origin_domain.label("origin_domain"),tbl_instance.load_avg.label("load_avg"),tbl_instance.event_id.label("event_id"),tbl_instance.status.label("status"),tbl_instance.last_updated_time.label("last_updated_time"),tbl_instance.instance_id.label("instance_id"),tbl_instance.privateip.label("privateip"),tbl_eip_mappings.eip.label("eip"),tbl_instance.active_connections.label("active_connections")).order_by(tbl_instance.active_connections.asc()).all()
				data=list(map(lambda x:x._asdict(),details))
				return data
			except Exception as e:
				self.event.log(e)
				return []

	def getIdsInPrometheusFormat(self,pg_response):
		instance_ids=""
		i=0

		if pg_response:
			for inst in pg_response:
				if i!=0:
					instance_ids+="|"
					pass
				instance_ids+=inst['instance_id']
				i+=1
		return instance_ids
	def leastConnectionInstanceFromDB(self,statusdata=[]):
		""" Get the least connetion instance from tbl_instance"""
		if statusdata:
			try:
				details=db.session.query(tbl_instance).join(tbl_eip_mappings,tbl_eip_mappings.attached_instance==tbl_instance.instance_id).with_entities(tbl_eip_mappings.eip.label("eip"),tbl_instance.load_avg.label("load_avg"),tbl_instance.event_id.label("event_id"),tbl_instance.last_updated_time.label("last_updated_time"),tbl_instance.instance_id.label("instance_id"),tbl_instance.privateip.label("privateip"),tbl_instance.public_ip.label("public_ip"),tbl_instance.active_connections.label("active_connections"),tbl_instance.priority.label("priority"),tbl_instance.status.label("status")).filter(tbl_instance.status.in_(statusdata),tbl_eip_mappings.is_protected==False).order_by(tbl_instance.active_connections.asc()).all()
				data=list(map(lambda x:x._asdict(),details))
				if data:
					return data[0]
				else:
					return None
			except Exception as e:
				self.event.log(e)
				return None
		else:
			try:
				details=db.session.query(tbl_instance).join(tbl_eip_mappings,tbl_eip_mappings.attached_instance==tbl_instance.instance_id).with_entities(tbl_eip_mappings.eip.label("eip"),tbl_instance.load_avg.label("load_avg"),tbl_instance.event_id.label("event_id"),tbl_instance.last_updated_time.label("last_updated_time"),tbl_instance.instance_id.label("instance_id"),tbl_instance.privateip.label("privateip"),tbl_instance.public_ip.label("public_ip"),tbl_instance.active_connections.label("active_connections"),tbl_instance.priority.label("priority"),tbl_instance.status.label("status")).filter(tbl_eip_mappings.is_protected==False).order_by(tbl_instance.active_connections.asc()).all()
				data=list(map(lambda x:x._asdict(),details))
				if data:
					return data[0]
				else:
					return None
			except Exception as e:
				self.event.log(e)
				return None

	def getInstanceFromLog(self,instance_id):
		if instance_id:
			try:
				key=configData.PROMETHEUS_KEY
				instance=db.session.query(tbl_instance_logs).with_entities(tbl_instance_logs.last_updated_time.label("last_updated_time")).filter(tbl_instance_logs.instance_id==instance_id).first()
				if instance:
					return instance
				else:
					return None
			except Exception as e:
				self.event.log(e)
				return None

	def delete(self,data):
		try:
			result = db.session.query(tbl_instance).filter(tbl_instance.instance_id == data['instance_id']).delete()
			db.session.commit()
		except Exception as e:
			self.event.log(e)
			return None

	def insert(self,tablename,data):
		try:
			if tablename:
				db.session.bulk_insert_mappings(tablename, [data])
				db.session.commit()			
		except Exception as e:
			self.event.log(e)
			return None

	
	def updateMetricData(self,instance,metric):
		""" updates the metric data to postgres db """
		try:
			con= int(float(metric['connections']))

			result = db.session.query(tbl_instance).filter(tbl_instance.instance_id == instance['instance_id']).one()
			result.active_connections = con
			result.last_updated_time=datetime.now()
			db.session.commit()
	
		except Exception as e:
			self.event.log(e)
			return None

	def updateLoadAvgMetric(self,instance,metric):
		""" updates the metric data to postgres db """
		try:	
			result = db.session.query(tbl_instance).filter(tbl_instance.instance_id == instance['instance_id']).one()
			result.load_avg = metric['load_avg']
			result.last_updated_time=datetime.now()
			db.session.commit()
		except Exception as e:
			self.event.log(e)
			return None

	def updateInstanceStatus(self,data):
		""" Updates the Status field inside tbl_instance """
		try:
			status = data.get("status")
			instance_id = data.get("instance_id")
			if instance_id:
				result = db.session.query(tbl_instance).filter(tbl_instance.instance_id == instance_id).one()
				result.status = status
				result.status_updated_time=datetime.now()
			else:
				result = db.session.query(tbl_instance).update({"status":status,"status_updated_time":datetime.now()})
			db.session.commit()
		except Exception as e:
			self.event.log(e)
			return None

	def updateEventStatus(self,data):
		""" Updates the Status field inside tbl_instance """
		try:
			if data['event_id']:
				result = db.session.query(tbl_events).filter(tbl_events.event_id == data['event_id']).one()
				result.event_status = data['event_status']
				result.last_updated_time = datetime.now()
			else:
				result = db.session.query(tbl_events).update({"event_status":data['event_status'],"last_updated_time":datetime.now()})
			db.session.commit()
			pass
		except Exception as e:
			self.event.log(e)
			return None

	def getEIPByStatus(self,statusdata):
		""" return eip by status """
		if statusdata:

			try:
				details=db.session.query(tbl_eip_mappings).with_entities(tbl_eip_mappings.attached_instance.label("attached_instance"),tbl_eip_mappings.origin_domain.label("origin_domain"),tbl_eip_mappings.eip_id.label("eip_id"),tbl_eip_mappings.is_protected.label("is_protected"),tbl_eip_mappings.eip.label("eip"),tbl_eip_mappings.status.label("status")).filter(tbl_eip_mappings.status==statusdata).order_by(tbl_eip_mappings.eip_id.asc()).all()
				data=list(map(lambda x:x._asdict(),details))
				if data:
					return data[0]
				else:
					return None
			except Exception as e:
				self.event.log(e)	
				return None
		else:
			try:
				details=db.session.query(tbl_eip_mappings).with_entities(tbl_eip_mappings.attached_instance.label("attached_instance"),tbl_eip_mappings.origin_domain.label("origin_domain"),tbl_eip_mappings.eip_id.label("eip_id"),tbl_eip_mappings.is_protected.label("is_protected"),tbl_eip_mappings.eip.label("eip"),tbl_eip_mappings.status.label("status")).all()
				data=list(map(lambda x:x._asdict(),details))
				return data
			except Exception as e:
				self.event.log(e)
				return None

	def addInstanceToEip(self,data):
		""" adding instance to eip """
		if data:
			try:
				result = db.session.query(tbl_eip_mappings).filter(tbl_eip_mappings.eip == data['eip']).one()
				result.status= data['status']
				result.last_updated_time=datetime.now()
				result.attached_instance=data['instance_id']
				result.attach_eventid=data['event_id']
				db.session.commit()

			except Exception as e:
				self.event.log(e)
				return None

	def updateEIPStatus(self,data):
		""" update the eip status """
		if data:
			try:
				result = db.session.query(tbl_eip_mappings).filter(tbl_eip_mappings.eip == data['eip']).one()
				result.status= data['status']
				result.last_updated_time=datetime.now()
				db.session.commit()
			except Exception as e:
				self.event.log(e)
				return None

	def removeInstanceFromEip(self,data):
		""" remove the instance from eip """
		if data:
			try:
				result = db.session.query(tbl_eip_mappings).filter(tbl_eip_mappings.eip == data['eip']).one()
				result.status= data['status']
				result.last_updated_time=datetime.now()
				result.attached_instance=""
				result.detach_eventid=data['event_id']
				db.session.commit()

			except Exception as e:
				self.event.log(e)
				return None


	def getAllEIP(self):
		""" returns all the eip's available """
		try:
			details=db.session.query(tbl_eip_mappings).join(tbl_instance,tbl_instance.instance_id==tbl_eip_mappings.attached_instance).with_entities(tbl_instance.last_updated_time.label("last_updated_time"),tbl_eip_mappings.origin_domain.label("origin_domain"),tbl_eip_mappings.playback_domain.label("playback_domain")).filter(tbl_instance.status=="ACTIVE").order_by(tbl_instance.active_connections).all()
			data=list(map(lambda x:x._asdict(),details))
			filteredData = self.filterByDate(data)
			if filteredData:
				endpoints = {}
				endpoints['origin']=filteredData[0]['origin_domain']
				endpoints['playback']=filteredData[0]['playback_domain']
				return endpoints,200
			else:
				return "No Data Available",400
		except Exception as e:
			raise DatabaseError(e)

	def updateInstanceEventId(self,instance_id,event_id):
		""" update instance event id """
		try:
			result = db.session.query(tbl_instance).filter(tbl_instance.instance_id == instance_id).one()
			result.event_id=event_id
			db.session.commit()
		except Exception as e:
			self.event.log(e)
			return None


	def getEventByStatus(self,statusdata=""):
		"""  returns the events by status """
		try:
			if statusdata:
				details=db.session.query(tbl_events).with_entities(tbl_events.activity.label("activity"),tbl_events.event_id.label("event_id"),tbl_events.event_status.label("event_status"),tbl_events.last_updated_time.label("last_updated_time")).filter(tbl_events.event_status==statusdata).all()
				data=list(map(lambda x:x._asdict(),details))
				if data:
					return data[0]
				else:
					return None
			else:
				details=db.session.query(tbl_events).with_entities(tbl_events.activity.label("activity"),tbl_events.event_id.label("event_id"),tbl_events.event_status.label("event_status"),tbl_events.last_updated_time.label("last_updated_time")).all()
				data=list(map(lambda x:x._asdict(),details))
				return data
		except Exception as e:
			self.event.log(e)
			return None

	def getInstanceByEventId(self,event_id=""):
		""" returns instances by Event Id """
		try:
			if event_id:
				details=db.session.query(tbl_instance).join(tbl_eip_mappings,tbl_eip_mappings.attached_instance==tbl_instance.instance_id).with_entities(tbl_eip_mappings.eip.label("eip"),tbl_instance.instance_id.label("instance_id"),tbl_instance.privateip.label("privateip")).filter(tbl_instance.event_id==event_id).all()
				data=list(map(lambda x:x._asdict(),details))			
				return data
			else:
				details=db.session.query(tbl_instance).join(tbl_eip_mappings,tbl_eip_mappings.attached_instance==tbl_instance.instance_id).with_entities(tbl_eip_mappings.eip.label("eip"),tbl_instance.instance_id.label("instance_id")).all()
				data=list(map(lambda x:x._asdict(),details))
				return data[0]
		except Exception as e:
			self.event.log(e)
			return None

	def filterByDate(self,data):
		filteredData = []
		if data:
			for instance in data:
				lastupdatedtime = instance['last_updated_time']
				if lastupdatedtime:
					currenttime = datetime.now()
					difference = currenttime - lastupdatedtime
					differenceInSeconds = difference.total_seconds()
					if configData.MAX_INSTANCE_DELAY > differenceInSeconds:
						filteredData.append(instance)
		return filteredData
		

	def getLastMailTime(self,instance_id):
		if instance_id:
			try:
				result=db.session.query(tbl_mail_alerts).with_entities(tbl_mail_alerts.last_mail_alert_time.label("last_mail_alert_time")).filter(tbl_mail_alerts.instance_id==instance_id).first()
				if result:
					return result[0]
				else:
					data={
						"instance_id":instance_id,
						"last_mail_alert_time":datetime.now()
					}   
					self.insert(tbl_mail_alerts,data)
					return data.last_mail_alert_time
			except Exception as e:
				self.event.log(e)
				return None

	def updateMailSendTime(self,instance_id):
		""" update last mail send time """
		try:
			result = db.session.query(tbl_mail_alerts).filter(tbl_mail_alerts.instance_id == instance_id).one()
			result.last_mail_alert_time=datetime.now()
			db.session.commit()
		except Exception as e:
			self.event.log(e)
			return None
				

	""" Sample Codes for testing purposes """

	def deleteEip(self,data):
		""" Delete an EIP """
		try:
			result = db.session.query(tbl_eip_mappings).filter(tbl_eip_mappings.eip == data['eip']).delete()
			db.session.commit()
		except Exception as e:
			self.event.log(e)
			return None

	def getInstanceLogs(self,instance_id=""):
		""" Read All Log data from tbl_instance_logs """
		try:
			if instance_id:
				details=db.session.query(tbl_instance_logs).with_entities(tbl_instance_logs.instance_log.label("instance_log"),tbl_instance_logs.event_id.label("event_id"),tbl_instance_logs.instance_id.label("instance_id")).filter(tbl_instance.instance_id==instance_id).all()
				data=list(map(lambda x:x._asdict(),details))
				return data
			else:
				details=db.session.query(tbl_instance_logs).with_entities(tbl_instance_logs.instance_log.label("instance_log"),tbl_instance_logs.event_id.label("event_id"),tbl_instance_logs.instance_id.label("instance_id")).all()
				data=list(map(lambda x:x._asdict(),details))
				return data			
		except Exception as e:
			self.event.log(e)
			return None
	
	def getEventLogsById(self,event_id=""):
		""" Read All Event data from tbl_event_logs """
		try:
			if event_id:
				details=db.session.query(tbl_event_logs).with_entities(tbl_event_logs.event_log.label("event_log")).filter(tbl_event_logs.event_id==event_id).all()
				data=list(map(lambda x:x._asdict(),details))			
				return data
			else:
				details=db.session.query(tbl_event_logs).with_entities(tbl_event_logs.event_log.label("event_log")).all()
				data=list(map(lambda x:x._asdict(),details))
				return data
		except Exception as e:
			self.event.log(e)
			return None
	
	def protectEip(self,eip=""):
		""" Protect Eip """
		if eip:
			try:
				result = db.session.query(tbl_eip_mappings).filter(tbl_eip_mappings.eip == eip).one()
				result.is_protected=True
				db.session.commit()
			except Exception as e:
				self.event.log(e)
				return None