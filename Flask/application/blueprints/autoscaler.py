from flask import Flask, request, json, Response, Blueprint, jsonify, current_app
from exceptions import APIError, RedisError, ConcsulError, AWSerror, ParameterError
from rediscalls import RedisConnection
from consulcalls import ConsulConnection
from utils import MicroServiceDiscovery
from autoscaler_utils import as_scaleup, as_scaledown, as_complete_lifecycle, attach_eip

autoscaler_blueprint = Blueprint('autoscaler', __name__)


@autoscaler_blueprint.route('/microservice')
def getservice_endpoint():
    """
    This is the method going to use in production for discovering other
    microservices
    """
    service = request.args.get('service')
    ms = MicroServiceDiscovery(current_app)
    service_endpoint, cache = ms.get_service_endpoint(service, cache=True)
    if service_endpoint:
        res = {service: service_endpoint, "cache": cache}
        return jsonify(res)
    else:
        res = {"error": "service not found"}
        return jsonify(res), 404


@autoscaler_blueprint.route('/health')
def healthcheck():
    data = {
        'status': 'healthy'
    }
    return jsonify(data)


@autoscaler_blueprint.route('/scaleup')
def scaleup():
    try:
        instance_count = int(request.args.get('count'))
        event_id = request.args.get('event_id')
    except Exception as e:
        raise ParameterError("parameters should be passed instance_count: int, event_id: uuid", original_exception=e)
    timeout = 120
    res = as_scaleup(instance_count, timeout, event_id, current_app)
    if res:
        return_body = {"instances": res}
        return jsonify(return_body), 200
    else:
        return_body = {"status": "Scaleup Failed"}
        return jsonify(return_body), 400


@autoscaler_blueprint.route('/scaledown')
def scaledown():
    """Endpoint for scaledown instances in autoscaling group"""
    try:
        instance_ids = request.args.get('instances')
        event_id = request.args.get('event_id')
        instance_ids_list = instance_ids.split(",")
        if (not (instance_ids and event_id)) or len(instance_ids) == 0:
            raise ParameterError(
                "parameters should be passed instances: list of instance ids to terminate, event_id: uuid")

    except Exception as e:
        raise ParameterError("parameters should be passed instances: list of instance ids to terminate, event_id: uuid",
                             original_exception=e)
    timeout = 120
    res = as_scaledown(instance_ids_list, timeout, event_id, current_app)
    if res:
        return_body = {"status": "instances terminated successfully"}
        return jsonify(return_body), 200
    else:
        return_body = {"status": "Termination failed"}
        return jsonify(return_body), 400


@autoscaler_blueprint.route('/confirmlifecycle')
def lifecycle():
    """End point to complete the lifecyclehook of a newly launched instance into
    autoscaling group, check: https://docs.aws.amazon.com/autoscaling/ec2/userguide/lifecycle-hooks.html"""
    timeout = 60
    try:
        instance_id = request.args.get('instance')
        event_id = request.args.get('event_id')
        hook_id = request.args.get('hook_id')
        hook_name = request.args.get('hook_name')
        if not (instance_id and event_id and hook_id and hook_name):
            raise ParameterError(
                "parameters should be passed instance: id of  instance , event_id: uuid, hook_id: id of lifecycle hook, hook_name: name of lifecycle hook")

    except Exception as e:
        raise ParameterError(
            "parameters should be passed instance: id of  instance , event_id: uuid, hook_id: id of lifecycle hook, hook_name: name of lifecycle hook",
            original_exception=e)

    res = as_complete_lifecycle(instance_id, event_id, hook_id, hook_name, timeout, current_app)
    if res:
        return_body = {"status": "SUCCESS"}
        return jsonify(return_body), 200
    else:
        return_body = {"status": "FAILED"}
        return jsonify(return_body), 400

@autoscaler_blueprint.route('/attacheip')
def attach_elastic_ip():
    """Endpoint for attaching the EIP to the instance"""
    try:
        instance_id = request.args.get('instance_id')
        event_id = request.args.get('event_id')
        eip = request.args.get('eip')
        if not (instance_id and event_id and eip):
            raise ParameterError(
                "parameters should be passed instance_id: id of  instance , event_id: uuid, allocation_id: id of eip allocation , eip: elastic ip")

    except Exception as e:
        raise ParameterError(
            "parameters should be passed instance_id: id of  instance , event_id: uuid, allocation_id: id of eip allocation , eip: elastic ip",
            original_exception=e)
    res = attach_eip(event_id, instance_id, eip, current_app)
    if res:
        return_body = {"status": "SUCCESS"}
        return jsonify(return_body), 200
    else:
        return_body = {"status": "FAILED"}
        return jsonify(return_body), 400
