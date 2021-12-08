from flask import Flask, request, json, Response, Blueprint, jsonify, current_app
from exceptions import APIError, RedisError, ConcsulError
from rediscalls import RedisConnection
from consulcalls import ConsulConnection
from utils import MicroServiceDiscovery, generate_uuid
from inspector_utils import Autoscaler
from tasks.bootstrap_checks import bootstrap_checks

frontend_blueprint = Blueprint('frontend', __name__)



@frontend_blueprint.route('/redis')
def getredisdata():
    """
    This is an example endpoint for getting and putting data into REDIS cache
    """
    key = request.args.get('key')
    rds = RedisConnection(current_app)
    value = rds.get_from_cache(key)
    if value is not None:
        data = {key: str(value)}
        data["cache"] = True
    else:
        data = {key: 'value is set manually'}
        rds.set_to_cache(key, data[key], 60)
    return jsonify(data)


@frontend_blueprint.route('/consul')
def getservice():
    """
    This is an example endpoint for getting the service endpoint using
    the consul service discovery API. consul API is called directly here
    """
    service = request.args.get('service')
    try:
        consul = ConsulConnection(current_app)
        service_endpoint = consul.disover_with_health(service)
    except Exception as e:
        raise ConcsulError('Got consul exception', original_exception=e)
    if service_endpoint:
        res = {"service_endpoint": service_endpoint}
        return jsonify(res)
    else:
        res = {"error": "service not found"}
        return jsonify(res), 404

@frontend_blueprint.route('/microservice')
def getservice_endpoint():
    """
    This is the method going to use in production for discovering other
    microservices
    """
    service = request.args.get('service')
    ms = MicroServiceDiscovery(current_app)
    service_endpoint, cache = ms.get_service_endpoint(service, cache=True)
    if service_endpoint:
        res = {service: service_endpoint,"cache": cache}
        return jsonify(res)
    else:
        res = {"error": "service not found"}
        return jsonify(res), 404

@frontend_blueprint.route('/scaleup')
def doscaleup():
    event_id = generate_uuid()
    scaler = Autoscaler(current_app)
    success, res = scaler.scaleup(1, event_id)
    """ This method returns the newly launched instance id along with lifecycle hook details
        The response is like. Before calling the autoscaler api for completing the lifecycle and
        finishing the launching of new instance, need to do the bootstrap checks on the newly launched
        instance.
        {
        "instances": [
        {
          "aws_id": "i-0b8e2d36eea22214b", 
          "hook_id": "1d8590d1-5c04-4966-a63c-559f160b5110", 
          "hook_name": "wolbf-stack-Aslifehook-1U5XJUI4MHYTB", 
          "private_ip": "172.31.24.21", 
          "public_ip": "18.218.114.173", 
          "status": "LAUNCHED"
         }
       ]
      }
    """

    if success:
        response = {"event_id": event_id, "instances": []}
        for instance in res['instances']:
            insert_instance_details_into_db(instance) # dummy method for inserting the newly launched instance details into the system
            #bootstrap_checks.delay(event_id, instance)  do the bootstrap checks and complete the lifecycle hook
            #asynchronously via celery worker
            bs = bootstrap_checks.delay(event_id, instance)
            #if bs:
            #    response['instances'].append({'instace_id': instance["aws_id"], "status": "LAUNCHED"})
            #
            #else:
            #    response['instances'].append({'instace_id': instance["aws_id"], "status": "BOOTSRAO_FAILED"})
            #
        return jsonify(response)
    else:
        response={"event_id": event_id, "status": "FAILED"}
        return jsonify(response), 400


@frontend_blueprint.route('/celerytest')
def celery_test():
    event_id = generate_uuid()
    instance_id = request.args.get('instance_id')
    instance = {'instance_id': instance_id, 'hook_name': 'testname', 'hook_id': 'test_id'}
    bootstrap_checks.delay(event_id, instance)
    response = {"event_id": event_id, "status": "OK"}
    return jsonify(response)


