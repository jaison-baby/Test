
from celery import shared_task
from datetime import datetime
import uuid
import secrets
import string
import os
import sys
from dbo import WolbfAPI
from config import config
from prometheus_dbo import PrometheusAPI
from utils import EventLogger
from flask import current_app
from inspector_utils import InspectorScaler

configData = config()


@shared_task
def updateInstanceMetric():
    obj = WolbfAPI()
    event_id = obj.generate_uuid()
    event = EventLogger(event_id, 'updateInstanceMetric', current_app)
    pg_response = obj.getInstancesByStatus(['ACTIVE', 'DRAIN'])
    no_of_instances = len(pg_response)

    prom_obj = PrometheusAPI()
    prom_response = prom_obj.getMetrics()
    no_of_metricsdata = len(prom_response)

    prom_load_avg = prom_obj.getInstantLoadAvg()

    if pg_response is not None:
        for instance in pg_response:
            try:
                if prom_response[instance[configData.PROMETHEUS_KEY]] is not None:
                    obj.updateMetricData(
                        instance, prom_response[instance[configData.PROMETHEUS_KEY]])

                if prom_load_avg[instance[configData.PROMETHEUS_KEY]] is not None:
                    obj.updateLoadAvgMetric(
                        instance, prom_load_avg[instance[configData.PROMETHEUS_KEY]])

            except KeyError:
                # case when Instance is there in PSQL , but no metric is collected in prometheus for that instance.
                lastupdatedtime = instance['last_updated_time']
                if lastupdatedtime:
                    currenttime = datetime.now()
                    difference = currenttime - lastupdatedtime
                    differenceInSeconds = difference.total_seconds()
                    # updateStatus()
                    if configData.MAX_METRIC_UPDATE_DELAY < differenceInSeconds:
                        log_text = "Max Timeout Reached!! Reason: An Instance is there in PSQL , but no metric is collected in prometheus for that instance.Instance id:{}. Instance may have stopped or is not running now".format(
                            instance['instance_id'])
                        last_mail_alert_time = obj.getLastMailTime(
                            instance[configData.PROMETHEUS_KEY])

                        if last_mail_alert_time:
                            difference = currenttime - last_mail_alert_time
                            differenceInSeconds = difference.total_seconds()
                            if configData.EMAIL_ALERT_DELAY < differenceInSeconds:
                                event.log(log_text)
                                event.alert(log_text, 'ERROR')
                                obj.updateMailSendTime(
                                    instance[configData.PROMETHEUS_KEY])
                                event.sendMail(log_text, 'ERROR',
                                               "Immediate Attention Required")
                                # event.addLogToDB(log_text, "error")
                                # scaler = InspectorScaler(current_app, event_id)
                                # scaler.removeInstance(
                                #     instance, log_text, "TIMEOUT")
    # case Instance is there in the prometheus response , but not in PSQL.

    if no_of_metricsdata != no_of_instances:
        for instance_id in prom_response:
            instance = obj.getInstanceFromLog(instance_id)
            if instance:
                l = len(instance)
                if l == 0:
                    log_text = "Max Timeout Reached!! Reason: Instance is there in the prometheus response , but not in PSQL.Instance id:{}".format(
                        instance_id)
                    event.log(log_text)
                    event.alert(log_text, 'ERROR')

                else:
                    lastupdatedtime = instance['last_updated_time']
                    if lastupdatedtime:
                        currenttime = datetime.now()
                        difference = currenttime - lastupdatedtime
                        differenceInSeconds = difference.total_seconds()
                        if configData.MAX_METRIC_UPDATE_DELAY < differenceInSeconds:
                            log_text = "Max Timeout Reached!! Reason: Instance is there in the prometheus response , but not in PSQL.Instance id:{}".format(
                                instance_id)
                            event.log(log_text)
                            event.alert(log_text, 'ERROR')

    return {"data": "done"}


def updateStatus(status, instance):
    # update status
    obj = WolbfAPI()
    data = {
        "status": status,
        "instance_id": instance['instance_id']
    }
    if instance['status'] == status:
        # no update required
        pass
    else:
        obj.updateInstanceStatus(data)
