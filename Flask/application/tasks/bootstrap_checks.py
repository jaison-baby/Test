from prometheus_dbo import PrometheusAPI
from exceptions import PrometheusError
from celery import shared_task
from flask import current_app
from inspector_utils import Autoscaler
from utils import EventLogger
from dbo import WolbfAPI
from models import tbl_instance_logs
from datetime import datetime
from inspector_utils import InspectorScaler


@shared_task
def bootstrap_checks(event_id: str, instance: dict):
    """ Method for doing the bootstrap checks on instnaces"""
    scaler = Autoscaler(current_app)
    timeout = current_app.config['BOOTSTRAP_TIMEOUT']
    instance_id = instance['instance_id']
    hook_name = instance['hook_name']
    hook_id = instance['hook_id']
    eip=instance['eip']
    event = EventLogger(event_id, 'bootstrapcheck', current_app)
    log_text="doing bootstrap check on instance {}".format(instance_id)
    event.log(log_text)
    event.addLogToDB(log_text,"info")

    check = False
    try:
        prom=PrometheusAPI()
        check = prom.bootstrap_check(instance_id, timeout)
    except PrometheusError as e:
        log_text = "Exception occurred  while doing the prometheus query for bootstrap check"
        base_format = event.base_format(log_text)
        current_app.logger.exception(base_format) # Logging the exception trace to the flask app log
        e_log_text = f'{log_text}, Exception is {e.original_exception}'
        event.alert(e_log_text, 'EXCEPTION')
        event.addLogToDB(log_text,"error")
        pass

    obj = WolbfAPI()

    if eip:
        if check:
            # bootsrap check passed, do the db operations here
            if scaler.attach_eip(instance_id,eip,event_id):
                obj.addInstanceToEip({'eip':eip,'instance_id':instance_id,'status':'ATTACHED','event_id':event_id})
                log_text = "Elastic ip attaching success for instance: {}".format(instance_id)
                event.log(log_text, "success")
                event.alert(log_text, 'INFO')
                event.addLogToDB(log_text,"success")
                if scaler.complete_lifecycle(instance_id, event_id, hook_id, hook_name):
                    #mark the instance as 'ACTIVE' also mark the event as success and complete
                    obj.updateInstanceStatus({"instance_id":instance_id,"status":"ACTIVE"})
                    obj.updateEventStatus({"event_id":event_id,"event_status":"COMPLETED"})
                    log_text = "lifecycle hook updation success for instance: {}".format(instance_id)
                    event.log(log_text, "success")
                    event.alert(log_text, 'INFO')   
                    event.addLogToDB(log_text,"success")
                else:
                    # Failed to update lifecyclehook, make the event as failed and update instance table as well
                    log_text = "lifecycle hook updation failed for instance: {}".format(instance_id)
                    updatefailure(event_id, log_text, instance, event)
            else:
                # Elastic ip attachment failed
                obj.updateEIPStatus({"status":"DETACHED","eip":eip})
                log_text = "Elastic ip attachment  failed for instance: {}".format(instance_id)
                updatefailure(event_id, log_text, instance, event)
        else:
            # bootsrap check failed, do the db operations here
            log_text = "Bootstrap checks failed for instance: {}".format(instance_id)
            updatefailure(event_id, log_text, instance, event)
    else:
        log_text="EIP NOT AVAILABLE"
        event.log(log_text)

def updatefailure(event_id, log_text, instance,event):
    event.log(log_text, "error")
    event.alert(log_text, 'ERROR')
    event.addLogToDB(log_text,"error")

    scaler = InspectorScaler(current_app,event_id)
    scaler.removeInstance(instance,log_text,"FAILED")
