from rediscalls import RedisConnection
from consulcalls import ConsulConnection
from flask import Flask
from exceptions import SlackError
import uuid
import requests
import json
from datetime import datetime
from models import tbl_event_logs
from flask_mail import Message,Mail



class MicroServiceDiscovery(object):
    """
    class that handles service discovery microservices
    first it will check in redis cache, if its not found get the service endpoint
    from consul and populate redis cache with ttl 60 seconds
    """

    def __init__(self, app: Flask):
        self.app = app
        self.redis = RedisConnection(app)
        self.consul = ConsulConnection(app)

    def get_service_endpoint(self, service: str, cache: bool = False) -> tuple:
        if cache:
            service_endpoint = self.redis.get_from_cache(service)
            if service_endpoint is not None:
                return str(service_endpoint), True
            else:
                service_endpoint = self.get_endpoint_from_consul(service)
                if service_endpoint:
                    self.redis.set_to_cache(service, service_endpoint, 60)
        else:
            service_endpoint = self.get_endpoint_from_consul(service)
        service_endpoint = service_endpoint if service_endpoint else service  # Returns service endpoint from consul if present , \
        # otherwise returns service name used for querying consul
        return service_endpoint, False

    def get_endpoint_from_consul(self, service) -> str:
        service_endpoint = self.consul.disover_with_health(service)
        return service_endpoint


def generate_uuid():
    uid = uuid.uuid4()
    return uid



class EventLogger(object):
    """This is a class for flask app logger operations. This wil help to avoid code repetation for generating event logs associated with an event"""

    def __init__(self, event_id, event_action, app):
        self.event_id = event_id
        self.event_action = event_action
        self.app = app
        self.mail = Mail(app)

    def base_format(self, message):
        base_info = "event_id: {}, event_action: {}, event_activity: {}, ".format(self.event_id, self.event_action,
                                                                                  message)
        return base_info

    def type_format(self, base_info, message_type):
        base_info + "status: {}".format(message_type)

    def log(self, message, message_type="info"):
        """This will logs into flask application logger object"""
        base_info = self.base_format(message)
        type_info = self.type_format(base_info, message_type)
        if message_type == 'success':
            self.app.logger.info(type_info)
        elif type == 'error':
            self.app.logger.error(type_info)
        else:
            self.app.logger.info(base_info)

    def alert(self, message, alert_level):
        """
            Parameters
            ----------
            message : str
                The actual message to send as alert
            alert_level : str
                The level of alert, options: 'info', 'exception', 'critical'
        """
        base_info = self.base_format(message)
        alert_message = base_info + "alert_level: {}".format(alert_level)
        if self.app.config['SLACK_NOTIFICATION']:
            slack_url = self.app.config['SLACK_URL']
            try:
                message_slack(slack_url, alert_message)
            except SlackError:
                error_text = "failed to send the following alert to slack, alert: {}".format(alert_message)
                self.app.logger.error(error_text)
                pass

    def addLogToDB(self,message,message_type="info"):
        from dbo import WolbfAPI

        event_description = "Event Log:{}".format(message_type)
        base_info = self.base_format(message)
        event_log={
            "event_id":self.event_id,
            "last_updated_time":datetime.now(),
            "event_description":event_description,
            "event_log":base_info
        }
        wolbf_obj = WolbfAPI()
        wolbf_obj.insert(tbl_event_logs,event_log)

    def sendMail(self,message="",message_type="info",subject="MagicPolygon Mail"):
        email_subject = "MagicPolygon:{}".format(message_type)+"-{}".format(subject)
        base_info = self.base_format(message)
        try:
            msg = Message(email_subject, sender =self.app.config['SENDER_EMAIL'], recipients = self.app.config['RECIPIENT_EMAILS'])
            msg.body = base_info
            self.mail.send(msg)
            return "Message sent!"
        except Exception as e:
            self.log(e)



def message_slack(slack_url, alert_message):
    slack_data = json.dumps({'text': alert_message})
    response = requests.post(
        slack_url, data=slack_data,
        headers={'Content-Type': 'application/json'}
    )
    if response.status_code != 200:
        raise SlackError




