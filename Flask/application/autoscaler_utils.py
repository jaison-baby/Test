import boto3
from botocore.exceptions import ClientError
import time
import json
from exceptions import AWSerror

as_group = 'wowza-as-cf'
sqs_queue_name = 'as-sqs'
client = boto3.client('autoscaling')
ec2 = boto3.client('ec2')
sqs = boto3.client('sqs')


def describe_instances(instance_ids, ec2=ec2):
    """response is the description of AWS instances with the given instance ids"""
    inst_response = ec2.describe_instances(InstanceIds=instance_ids)
    instances_response = [(inst['InstanceId'], inst.get('LaunchTime'), inst['Placement']['AvailabilityZone'],
                           inst.get('PublicIpAddress'), inst.get('PrivateIpAddress')) for
                          reservation in inst_response['Reservations'] for inst in reservation['Instances']]
    return instances_response


def desiredcount(as_group, client=client):
    """checking the current desired instance count in the given autoscaling grouo"""
    response = client.describe_auto_scaling_groups(AutoScalingGroupNames=[as_group])
    desired_count = response['AutoScalingGroups'][0]['DesiredCapacity']
    instances = [instance['InstanceId'] for instance in response['AutoScalingGroups'][0]['Instances'] if
                 instance['LifecycleState'] == 'InService']
    return (desired_count, instances)


def get_queue_url(queue_name):
    """Get the sqs queue url"""
    response = sqs.get_queue_url(
        QueueName=queue_name,
    )
    return response["QueueUrl"]


class Event(object):
    """This is a class for flask app logger operations. This wil help to avoid code repetation for generating event logs associated with an event"""

    def __init__(self, event_id, event_action, app):
        self.event_id = event_id
        self.event_action = event_action
        self.app = app

    def base_format(self, message):
        base_info = "event_id: {}, event_action: {}, event_activity: {}, ".format(self.event_id, self.event_action,
                                                                                  message)
        return base_info

    def log(self, message, type="info"):
        """This will logs into flask application logger object"""
        base_info = self.base_format(message)
        if type == 'success':
            self.app.logger.info(base_info + "status: {}".format('success'))
        elif type == 'error':
            self.app.logger.error(base_info + "status: {}".format('error'))
        else:
            self.app.logger.info(base_info)


def as_scaleup(count, timeout, event_id, app):
    """ Method to scale up AWS autoscaling group by increasing the 'desired capacity'
    parameter of an autoscaling group"""
    event = Event(event_id, 'scaleup', app)
    try:
        sqsdeleteall(queue_url)  # Delete all messages in the sqs to make sure we are not processing any old messages
        event.log("Deleted all obsolete messages in SQS queue", 'success')
    except Exception as e:
        base_format = event.base_format("Failed to delete all obsolete messages in SQS queue")
        raise AWSerror(base_format, original_exception=e)

    desired_count, instances = desiredcount(as_group)
    new_count = (desired_count + count)
    event.log("Changing desired capacity to {}".format(new_count))
    try:
        response = client.set_desired_capacity(
            AutoScalingGroupName=as_group,
            DesiredCapacity=new_count,
            HonorCooldown=False
        )
        if response:
            event.log("changed autoscaling group desired capacity", "success")
    except Exception as e:
        base_format = event.base_format("Failed to change autoscaling group desired capacity")
        raise AWSerror(base_format, original_exception=e)

    timer = 0
    event.log("Waiting for SQS messages with launched instance details")
    while timer < timeout:
        try:
            messages = sqsget(queue_url)
        except Exception as e:
            base_format = event.base_format("SQS message Retrieval FAILED")
            raise AWSerror(base_format, original_exception=e)

        if messages:
            instances = []
            for message in messages:
                instance_id = message['EC2InstanceId']
                hook_id = message['LifecycleActionToken']
                hook_name = message['LifecycleHookName']
                instance_details = describe_instances([instance_id])  # Get the instance details from AWS
                if instance_id == instance_details[0][0]:
                    instance_dict = {}
                    instance_dict['aws_id'] = instance_id
                    instance_dict['status'] = 'LAUNCHED'
                    instance_dict['public_ip'] = instance_details[0][3]
                    instance_dict['private_ip'] = instance_details[0][4]
                    instance_dict['hook_id'] = hook_id
                    instance_dict['hook_name'] = hook_name
                    event.log("New instance message received in SQS details: {}".format(instance_dict))
                    instances.append(instance_dict)
            return instances
        else:
            timer += 20
    base_format = event.base_format("Timeout occurred while doing the autoscaling process")
    raise AWSerror(base_format)


def checkiflaunched(new_count):
    print("Checking if new instance(s) launched in to AS group")
    desired_count, instances = desiredcount(as_group, client)
    if len(instances) == new_count:
        print("Scaling Success")
        return True
    else:
        return False


def as_scaledown(instances, timeout, event_id, app):
    """ Method to scaledown by terminating the given instances"""
    event = Event(event_id, 'scaledown', app)
    for instance in instances:
        event.log("Terminating instance {}".format(instance))
        try:
            response = client.terminate_instance_in_auto_scaling_group(
                InstanceId=instance,
                ShouldDecrementDesiredCapacity=True
            )
        except ClientError as e:
            if 'No managed instance found for instance ID' in e.response['Error']['Message']:
                event.log("Instance {} not found. Instance may already deleted".format(instance))
                continue
            else:
                base_format = event.base_format("Instance {} termination failed".format(instance))
                raise AWSerror(base_format, original_exception=e)

        if response:
            activity_id = response['Activity']['ActivityId']
            log_string = "Instance {} termination API call success, waiting for completing the termination, activity_id: {}".format(
                instance, activity_id)
            event.log(log_string, "success")
            timer = 0
            while timer < timeout:
                activity = None
                try:
                    activity = client.describe_scaling_activities(
                        ActivityIds=[
                            activity_id
                        ],
                        AutoScalingGroupName=as_group
                    )
                    if activity['Activities'][0]['StatusCode'] == 'Successful':
                        event.log("Instance {} terminated successfully".format(instance))
                        break
                except Exception as e:
                    base_format = event.base_format(
                        "Instance {} termination confirmation activity failed".format(instance))
                    raise AWSerror(base_format, original_exception=e)
                timer += 10
                time.sleep(10)
            else:
                base_format = event.base_format("Timeout occurred for terminating instance {}".format(instance))
                raise AWSerror(base_format)
    return True


def as_complete_lifecycle(instance_id, event_id, hook_id, hook_name, timeout, app):
    event = Event(event_id, 'lifecyclehook', app)
    try:
        completelifecyle(instance_id, hook_id, hook_name)
        event.log("Life cycle hook completed for instance {}".format(instance_id))
    except Exception as e:
        base_format = event.base_format(
            "Instance {} lifecycle hook confirmation activity failed".format(instance_id))
        raise AWSerror(base_format, original_exception=e)
    event.log("checking if instance {} is active in AS group".format(instance_id))
    """To do: check the status of instance and make sure its in active"""
    return True


def sqsget(url):
    response = sqs.receive_message(
        QueueUrl=url,
        AttributeNames=[
            'ApproximateNumberOfMessages',
        ],
        MessageAttributeNames=[
            'All',
        ],
        MaxNumberOfMessages=10,
        VisibilityTimeout=30,
        WaitTimeSeconds=20,
    )
    if response.get('Messages'):
        print("message %s" % response)
        sqs_messages = []
        for message in response['Messages']:
            body = json.loads(message['Body'])
            if body['LifecycleTransition'] == 'autoscaling:EC2_INSTANCE_LAUNCHING':
                sqs_messages.append(body)
            sqsdelete(url, message['ReceiptHandle'])
        return sqs_messages
    else:
        print("No message in SQS")
        return False


def sqsdelete(url, handle):
    sqs.delete_message(
        QueueUrl=url,
        ReceiptHandle=handle
    )


def sqsdeleteall(url):
    response = sqs.receive_message(
        QueueUrl=url,
        AttributeNames=[
            'ApproximateNumberOfMessages',
        ],
        MessageAttributeNames=[
            'All',
        ],
        MaxNumberOfMessages=10,
        VisibilityTimeout=30,
        WaitTimeSeconds=5,
    )
    if response.get('Messages'):
        print("Deleting all  SQS messages")
        for message in response['Messages']:
            sqsdelete(url, message['ReceiptHandle'])


def sqsresphandle(response):
    return response['ReceiptHandle']


def completelifecyle(instance_id, hook_id, hook_name):
    client.complete_lifecycle_action(
        LifecycleHookName=hook_name,
        AutoScalingGroupName=as_group,
        LifecycleActionToken=hook_id,
        LifecycleActionResult='CONTINUE',
        InstanceId=instance_id
    )

def attach_eip(event_id, instance_id, eip, app):
    event = Event(event_id, 'eip_attach', app)
    try:
        res = ec2.associate_address(
            InstanceId=instance_id,
            PublicIp=eip,
            AllowReassociation=False
        )
        if res['AssociationId']:
            return True
            event.log("EIP: {} attached to the instance {}".format(eip, instance_id))
    except Exception as e:
        base_format = event.base_format(
        "Failed to attach EIP {} to the instance {}".format(eip, instance_id))
        raise AWSerror(base_format, original_exception=e)
    event.log("Failed to attach EIP {} to the instance {}".format(eip, instance_id))
    return False

queue_url = get_queue_url(sqs_queue_name)

