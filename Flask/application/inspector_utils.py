from flask import Flask
from utils import MicroServiceDiscovery
import uuid
import requests
from dbo import WolbfAPI
from prometheus_dbo import PrometheusAPI
from models import tbl_instance, tbl_instance_logs, tbl_events
from datetime import date, datetime
from utils import EventLogger
from config import config

configData = config()
last_mail_alert_time = datetime.now()


class Autoscaler(object):
    def __init__(self, app: Flask):
        self.app = app
        self.timeout = app.config['AUTOSCALER_API_TIMEOUT']
        self.wolbf_obj = WolbfAPI()

    def _get_service_endpoint(self, catalog: str) -> str:
        """ Get the uri of autoscaler for corresponding endpoint. Avaulable endpoints are
        'scaleup','scaledown','lifecycle_completion' """
        app = self.app
        ms = MicroServiceDiscovery(app)
        autoscaler_service_name = app.config['AUTOSCALER_SERVICE_NAME']
        service_endpoint, cache = ms.get_service_endpoint(
            autoscaler_service_name, cache=True)
        endpoint_uri = "{}{}".format(
            service_endpoint, app.config['AUTOSCALER_ENDPOINTS'][catalog])
        return endpoint_uri

    def scaleup(self, count: int, event_id: uuid) -> tuple:
        timeout = self.timeout
        scaleup_endpoint = self._get_service_endpoint('scaleup')
        print(scaleup_endpoint)
        # call the scaleup api of autoscaler service
        params = {'count': count, 'event_id': event_id}
        print(params)
        res = requests.get(url=scaleup_endpoint,
                           params=params, timeout=timeout)
        if res.status_code == 200:  # scaleup is success and returns lifecycle hook details
            return True, res.json()
        elif res.status_code == 400:  # scaleup is not success
            return False, res.json()
        else:
            return False, {"status": "error", "message": "server error"}

    def scaledown(self, event_id: uuid, instances: str) -> tuple:
        timeout = self.timeout
        scaledown_endpoint = self._get_service_endpoint('scaledown')
        # call the scaledown api of autoscaler service
        params = {'instances': instances, 'event_id': event_id}
        res = requests.get(url=scaledown_endpoint,
                           params=params, timeout=timeout)
        if res.status_code == 200:  # scaleup is success and returns lifecycle hook details
            return True, res.json()
        elif res.status_code == 400:  # scaleup is not success
            return False, res.json()
        else:
            return False, {"status": "error", "message": "server error"}

    def complete_lifecycle(self, instance_id, event_id, hook_id, hook_name):
        timeout = self.timeout
        lifecycle_endpoint = self._get_service_endpoint('lifecycle_completion')
        params = {'instance': instance_id, 'event_id': event_id,
                  'hook_id': hook_id, 'hook_name': hook_name}
        res = requests.get(url=lifecycle_endpoint,
                           params=params, timeout=timeout)
        if res.status_code == 200:  # lifecycle hook completed
            return True
        else:
            return False

    def attach_eip(self, instance_id, eip, event_id):
        timeout = self.timeout
        eip_attaching_endpoint = self._get_service_endpoint(
            'eip_attach_endpoint')
        params = {'instance_id': instance_id, 'eip': eip, 'event_id': event_id}
        res = requests.get(url=eip_attaching_endpoint,
                           params=params, timeout=timeout)
        if res.status_code == 200:  # eip attached successfully
            res = res.json()
            if res["status"] == "SUCCESS":
                return True
            else:
                return False
        else:
            return False


class InspectorScaler(object):
    """ Scale """

    def __init__(self, app: Flask, event_id):
        self.app = app
        self.wolbf_obj = WolbfAPI()
        self.scaler = Autoscaler(self.app)
        self.timeout = app.config['AUTOSCALER_API_TIMEOUT']
        self.event_id = event_id
        self.event = EventLogger(event_id, 'InspectorScaler', app)

    def scaleupRequest(self, eip):
        """ scaleup request """
        event_data = {
            "event_id": self.event_id,
            "start_time": datetime.now(),
            "activity": "SCALEUP",
            "activity_descriptions": "Scaleup Requested at %s" % (datetime.now()),
            "event_status": "INPROGRESS",
            "last_updated_time": datetime.now()
        }
        self.wolbf_obj.insert(tbl_events, event_data)
        log_text = "Scaleup Requested: inprogress event {}".format(
            self.event_id)
        self.event.log(log_text)
        self.event.addLogToDB(log_text)
        success, res = self.scaler.scaleup(1, self.event_id)
        if success & success == True:
            self.scaleupSuccess(res, eip)
        else:
            self.scaleupFailure(eip)

    def scaleupSuccess(self, response, eip):
        """ scaleup success """
        from tasks.bootstrap_checks import bootstrap_checks

        prom_obj = PrometheusAPI()
        if response:
            for instance in response['instances']:
                instance_id = instance['aws_id']
                data = {
                    "instance_id": instance_id,
                    "event_id": self.event_id,
                    "privateip": instance['private_ip'],
                    "public_ip": instance['public_ip'],
                    "launch_time": datetime.now(),
                    "status": "BOOTSTRAPPING",
                    "priority": 1,
                    "status_updated_time": datetime.now()
                }
                self.wolbf_obj.insert(tbl_instance, data)
                log_text = "Scaleup Request Success, Received message from SNS. instance: {}".format(
                    instance_id)
                self.event.log(log_text)
                self.event.addLogToDB(log_text)
                instance = {'private_ip': instance['private_ip'], 'instance_id': instance_id,
                            'hook_name': instance['hook_name'], 'hook_id': instance['hook_id'], 'eip': eip}
                bootstrap_checks.delay(self.event_id, instance)
        else:
            self.event.log("No instance received from scale up request")

    def scaleupFailure(self, eip):
        """ scaleup failure """
        event_data = {"event_id": self.event_id, "event_status": "FAILED"}
        log_text = "Scaleup Failed: event_id {}".format(self.event_id)
        self.event.log(log_text)
        self.event.addLogToDB(log_text)
        self.wolbf_obj.updateEventStatus(event_data)
        self.wolbf_obj.removeInstanceFromEip(
            {'eip': eip, 'status': 'DETACHED', 'event_id': self.event_id})

    def scaledownRequest(self, instance):
        """ scaledown request """
        event_data = {
            "event_id": self.event_id,
            "start_time": datetime.now(),
            "activity": "SCALEDOWN",
            "activity_descriptions": "Scaledown Requested at %s" % (datetime.now()),
            "event_status": "INPROGRESS",
            "last_updated_time": datetime.now()
        }
        self.wolbf_obj.insert(tbl_events, event_data)

        success, res = self.scaler.scaledown(
            self.event_id, instance['instance_id'])
        log_text = "ScaleDown Requested: event_id {}".format(self.event_id)

        self.event.log(log_text)
        self.event.addLogToDB(log_text)
        if success and success == True:
            self.scaledownSuccess(instance)
        else:
            self.scaledownFailure(instance)

    def scaledownSuccess(self, instance):
        """ scaledown success function """
        status = "COMPLETED"
        log_text = "SCALEDOWN:SUCCESS, total connections: %s,  load_avg: %s" % (
            instance["active_connections"], instance["load_avg"]),
        data = {"log_text": log_text, "instance": instance, "status": status}
        self.dbUpdations(data)

    def scaledownFailure(self, instance):
        """ scaledown failure function """
        status = "FAILED"
        log_text = "SCALEDOWN:FAILED, total connections: %s, load_avg: %s" % (
            instance["active_connections"], instance["load_avg"]),
        data = {"log_text": log_text, "instance": instance, "status": status}
        self.dbUpdations(data)

    def dbUpdations(self, data):
        self.event.log(data['log_text'], 'info')
        self.event.addLogToDB(data['log_text'])
        self.removeInstance(data['instance'], data['log_text'], data['status'])

    def removeInstance(self, instance, log_text, status):
        """ function to remove instance from db and detaching eip """
        if instance:
            event_data = {"event_id": self.event_id, "event_status": status}
            logdata = {
                'instance_id': instance["instance_id"],
                'event_id': self.event_id,
                'privateip': instance["privateip"],
                'last_updated_time': datetime.now(),
                'instance_log': log_text,
                'eip': instance['eip']
            }
            self.wolbf_obj.removeInstanceFromEip(
                {'eip': instance['eip'], 'status': 'DETACHED', 'event_id': self.event_id})
            self.wolbf_obj.insert(tbl_instance_logs, logdata)
            self.wolbf_obj.delete({"instance_id": instance["instance_id"]})
            self.wolbf_obj.updateEventStatus(event_data)

    def checkEipAndDoScaleUp(self):
        """ This function checks the available eip and changes its status to ASSOCIATING """
        self.event.log("Checking eip")
        elasticIp = self.wolbf_obj.getEIPByStatus("DETACHED")
        if elasticIp:
            eip = elasticIp['eip']
            self.wolbf_obj.updateEIPStatus(
                {"status": "ASSOCIATING", "eip": eip})
            self.scaleupRequest(eip)
        else:
            self.event.log("No EIP Available")

    def switchLeastToDrain(self, instance_id):
        """ switches the least available instance to drain """
        self.event.log("Switching instance to Drain: {}".format(instance_id))
        activedata = {
            "status": "ACTIVE",
            "instance_id": ""
        }
        draindata = {
            "status": "DRAIN",
            "instance_id": instance_id
        }
        self.wolbf_obj.updateInstanceStatus(activedata)
        self.wolbf_obj.updateInstanceStatus(draindata)

    def switchDrainToActiveAndCompleteEvent(self, instance):
        """ Switches Drain to Active and Complete Scale up Event """

        self.wolbf_obj.updateInstanceStatus(
            {"instance_id": instance["instance_id"], "status": "ACTIVE"})
        event_data = {
            "event_id": self.event_id,
            "start_time": datetime.now(),
            "activity": "SCALEUP",
            "activity_descriptions": "Changing instance from DRAIN To ACTIVE. Requested at {}".format(datetime.now()),
            "event_status": "COMPLETED",
            "last_updated_time": datetime.now()
        }
        self.wolbf_obj.insert(tbl_events, event_data)
        log_text = "new scaleup event occured,changing the status of the instance from drain to active and moving the info about the current instance to instance logs table"
        logdata = {
            'instance_id': instance["instance_id"],
            'event_id': instance["event_id"],
            'privateip': instance["privateip"],
            'last_updated_time': datetime.now(),
            'instance_log': log_text,
            'eip': instance['eip']
        }
        self.wolbf_obj.insert(tbl_instance_logs, logdata)
        self.wolbf_obj.updateInstanceEventId(
            instance['instance_id'], self.event_id)

    def checkForEventTimeout(self, event_info):
        """ function checks the event time exceeds the timeout for waiting an scaleup/scaledown event """
        lastupdatedtime = event_info['last_updated_time']
        if lastupdatedtime:
            currenttime = datetime.now()
            difference = currenttime - lastupdatedtime
            differenceInSeconds = difference.total_seconds()
            if configData.MAX_EVENT_UPDATE_DELAY < differenceInSeconds:
                log_text = " Instance data removed. Reason: Event timeout exceeded"
                instance = self.wolbf_obj.getInstanceByEventId(
                    event_info['event_id'])
                if instance:
                    self.removeInstance(instance[0], log_text, "TIMEOUT")
                else:
                    self.event.log(
                        "Changing Event Status. Reason: Event timeout exceeded")
                    event_data = {
                        "event_id": event_info['event_id'], "event_status": "TIMEOUT"}
                    eip = self.wolbf_obj.getEIPByStatus("ASSOCIATING")
                    if eip:
                        self.wolbf_obj.removeInstanceFromEip(
                            {'eip': eip['eip'], 'status': 'DETACHED', 'event_id': event_info['event_id']})
                        self.wolbf_obj.updateEventStatus(event_data)
                    else:
                        self.wolbf_obj.updateEventStatus(event_data)
        else:
            self.event.log("Last updated time not found for the event")

    def getDifferencePercentage(self, avg_of_instances, scaleStatus):
        """ get the difference percentage """
        if scaleStatus == "scaleup":
            difference = avg_of_instances - configData.AUTOSCALING_THRESHOLD_COUNT
        else:
            difference = configData.AUTOSCALING_THRESHOLD_COUNT - avg_of_instances

        diff_precentage = (
            float((difference / configData.AUTOSCALING_THRESHOLD_COUNT))*100)
        return diff_precentage

    def getPostgressInstanceIDs(self, status=[]):
        pg_response = self.wolbf_obj.getInstancesByStatus(status)
        pg_instances = len(pg_response)
        instance_ids = self.wolbf_obj.getIdsInPrometheusFormat(pg_response)
        return pg_instances, instance_ids

    def checkForScaleup(self, prom_active_instances):
        # check if there is any available instance in drain status, then switch it to active
        instance = self.wolbf_obj.leastConnectionInstanceFromDB(["DRAIN"])
        if instance:
            self.event.log('switching drain to active')
            self.switchDrainToActiveAndCompleteEvent(instance)
        else:
            maxInstances = configData.MAX_NO_OF_INSTANCES
            if prom_active_instances >= maxInstances:
                log_text = "Scaleup reached maximum limit"
                global last_mail_alert_time
                if last_mail_alert_time:
                    currenttime = datetime.now()
                    diff = currenttime - last_mail_alert_time
                    differenceInSeconds = diff.total_seconds()
                    print("Current:{} and Last: {}".format(
                        currenttime, last_mail_alert_time))
                    print("Difference in Seconds {}".format(differenceInSeconds))
                    if configData.EMAIL_ALERT_DELAY < differenceInSeconds:
                        last_mail_alert_time = currenttime
                        self.event.log(log_text)
                        self.event.alert(log_text, 'ERROR')
                        self.event.sendMail(
                            log_text, 'ALERT', "Scaleup Reached Maximum Limit")

            else:
                self.event.log('checking eip for scaleup')
                self.checkEipAndDoScaleUp()

    def getTheSumOfInstances(self, instance_ids="", parameter=""):
        """ get the sum of instances """
        prom_obj = PrometheusAPI()
        if instance_ids:
            if parameter == "connection":
                prom_response = prom_obj.getInstanceMetricSum(instance_ids)
                if prom_response:
                    prom_instances = int(prom_response['no_of_instances'])
                    sum_of_instances = int(prom_response['sum'])
                    return prom_instances, sum_of_instances
                else:
                    return None, None
            else:
                prom_response = prom_obj.getAverageSumOfLoadAvg(instance_ids)
                if prom_response:
                    prom_instances = int(prom_response['no_of_instances'])
                    sum_of_instances = float(prom_response['sum'])
                    return prom_instances, sum_of_instances
                else:
                    return None, None
        else:

            return None, None

    def checkLoadAvgOfInstances(self, instance_ids, checkNewAvg=False):
        """ check the avg load of instances and return a boolean """
        sum_of_instances = 0.0
        avg_of_instances = 0.0
        newAverage = 0.0
        prom_instances, sum_of_instances = self.getTheSumOfInstances(
            instance_ids, "load")
        check = True
        if sum_of_instances:
            avg_of_instances = sum_of_instances/prom_instances
            if avg_of_instances < configData.AUTOSCALING_THRESHOLD_LOAD:
                check = True
                if checkNewAvg == True:
                    if (prom_instances-1) != 0:
                        newAverage = sum_of_instances/(prom_instances-1)
                        self.event.log("newAverage :{}".format(newAverage))
                        if newAverage < configData.AUTOSCALING_THRESHOLD_LOAD:
                            check = True
                        else:
                            check = False
                    else:
                        check = False
            else:
                check = False
            return check

    def switchToDrainAndScaleDown(self):
        """ Switch to Drain and Scaledown """
        leastCountInstance = self.wolbf_obj.leastConnectionInstanceFromDB()
        if leastCountInstance:
            if leastCountInstance['status'] == "DRAIN":
                # donothing
                pass
            else:
                self.switchLeastToDrain(leastCountInstance['instance_id'])

            if leastCountInstance['active_connections'] <= configData.MIN_SCALEDOWN_CONNECTIONS:
                # scale down
                self.scaledownRequest(leastCountInstance)

    def checkForScaledown(self):
        pg_data = self.wolbf_obj.getInstancesByStatus(['ACTIVE', 'DRAIN'])
        instance_ids = self.wolbf_obj.getIdsInPrometheusFormat(pg_data)
        prom_instances, sum_of_instances = self.getTheSumOfInstances(
            instance_ids, "connection")
        self.event.log("on Scale down logic")
        self.event.log("No of all Instances:{}".format(prom_instances))
        self.event.log("new connection Sum :{}".format(sum_of_instances))
        if prom_instances > configData.MIN_NO_OF_INSTANCES:
            if sum_of_instances and sum_of_instances != 0:
                avg_of_instances = sum_of_instances/prom_instances
                if (prom_instances - 1) != 0:
                    newAverage = sum_of_instances/(prom_instances - 1)
                    self.event.log("newAverage: {}".format(newAverage))
                    if newAverage < configData.AUTOSCALING_THRESHOLD_COUNT:
                        load_avg = self.checkLoadAvgOfInstances(
                            instance_ids, True)
                        self.event.log("load avg Second: {}".format(load_avg))
                        if load_avg == True:
                            if self.getDifferencePercentage(avg_of_instances, "scaledown") >= configData.PERCENTAGE_THRESHOLD:
                                self.switchToDrainAndScaleDown()
            else:
                if sum_of_instances == 0:
                    self.switchToDrainAndScaleDown()
