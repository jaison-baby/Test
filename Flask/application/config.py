import os

BASEDIR = os.path.abspath(os.path.dirname(__name__))


class Config(object):
    DEBUG = True
    SECRET_KEY = os.getenv("SECRET_KEY", os.urandom(16).hex())
    AUTOSCALER_SERVICE_NAME = os.environ.get('AUTOSCALER_SERVICE_NAME', "wolbf_autoscaler")
    INSPECTOR_SERVICE_NAME = os.environ.get('INSPECTOR_SERVICE_NAME', "wolbf_inspector")
    AUTOSCALER_SCALEUP_URL = os.environ.get('AUTOSCALER_SCALEUP_URL', "/v1/autoscaler/scaleup")
    AUTOSCALER_API_TIMEOUT = 180
    AUTOSCALER_ENDPOINTS = {'scaleup': '/v1/autoscaler/scaleup',
                            'lifecycle_completion': '/v1/autoscaler/confirmlifecycle',
                            'scaledown': '/v1/autoscaler/scaledown', 'eip_attach_endpoint': '/v1/autoscaler/attacheip'}

    MAIL_SERVER='smtp-relay.gmail.com'
    MAIL_PORT = 465
    MAIL_USERNAME = "hello@magicpolygon.com"  #os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = "jsuhvzmasgwbbypb"  #os.environ.get("MAIL_PASSWORD")
    MAIL_USE_TLS = False
    MAIL_USE_SSL = True
    SENDER_EMAIL="hello@magicpolygon.com"
    RECIPIENT_EMAILS=["daniel@sparksupport.com","swaroski.anan@gmail.com"]

class DevelopmentConfig(Config):
    DEBUG = True
    dbuser = os.environ.get('DATABASE_USER', "wolbf")
    dbname = os.environ.get('DATABASE_NAME', "wolbf")
    dbpass = os.environ.get('DATABASE_PASSWORD', "wolbf")
    dbhost = "pg"  # os.environ.get('DATABASE_HOST',"127.0.0.1")
    dbport = "5432"
    SQLALCHEMY_DATABASE_URI = "postgresql+psycopg2://" + dbuser + ":" + dbpass + "@" + dbhost + ":"+dbport+"/" + dbname
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    REDIS_HOST = os.environ.get("REDIS_HOST")
    REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD")
    REDIS_PORT = os.environ.get("REDIS_PORT")
    BROKER_URL = os.environ.get('REDIS_URL', "redis://{user}:{password}@{host}:{port}/0".format(
        user='wolbf', password=str(REDIS_PASSWORD), host=str(REDIS_HOST), port=str(REDIS_PORT)))
    CELERY_RESULT_BACKEND = BROKER_URL
    
    PROMETHEUS_URL = os.environ.get('PROMETHEUS_URL',"localhost")
    # PROMETHEUS_AVERAGE_INTERVAL = os.environ.get('PROMETHEUS_INTERVAL','5m')
    # PROMETHEUS_INSTANT_INTERVAL = os.environ.get('PROMETHEUS_INTERVAL','1m')
    PROMETHEUS_AVERAGE_INTERVAL = "4s"
    PROMETHEUS_INSTANT_INTERVAL = "4s"

    PROMETHEUS_KEY = "instance_id"

    BOOTSTRAP_TIMEOUT = 120
    #Notification configs
    SLACK_NOTIFICATION = True
    SLACK_URL = os.environ.get("SLACK_URL")

    # max threshold connections
    AUTOSCALING_THRESHOLD_COUNT=45
    # max threshold load
    AUTOSCALING_THRESHOLD_LOAD=0.9
    # maximum timout for metrics update
    MAX_METRIC_UPDATE_DELAY=180
    # maximum event timout for metrics update
    MAX_EVENT_UPDATE_DELAY=180
    # minimum no of instances which are to be there in the server
    MIN_NO_OF_INSTANCES=1
    # percentage threshold value takes the given percentage of AUTOSCALING_THRESHOLD_COUNT 
    PERCENTAGE_THRESHOLD=0
    # maximum no of instances that are to be scaled up
    MAX_NO_OF_INSTANCES=3
    # count of active connections to start scale down
    MIN_SCALEDOWN_CONNECTIONS=0
    # limit to check whether an least instance is still running
    MAX_INSTANCE_DELAY=30
    # email alert delay in seconds for sending email alerts when server goes down
    EMAIL_ALERT_DELAY=60

class ProductionConfig(Config):
    pass


# return active config
available_configs = dict(development=DevelopmentConfig, production=ProductionConfig)
selected_config = os.getenv("FLASK_ENV", "development")
config = available_configs.get(selected_config, "production")

# Create Celery beat schedule:
# celery_get_manifest_schedule = {
#     'schedule-name': {
#         'task': 'application.tasks.add_together',
#         'schedule': 1,
#     },
# }
