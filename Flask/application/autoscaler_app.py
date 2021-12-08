from flask_sqlalchemy import SQLAlchemy
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_restful import Resource, Api
from sqlalchemy.engine import create_engine
from sqlalchemy import event, inspect, orm
from flask_migrate import Migrate
from blueprints.autoscaler import autoscaler_blueprint
from exceptions import CustomErrorHandlers, RedisError
import os
from config import config
import redis
from celery import Celery
import celeryconfig


def connect_redis(app):
    redis_host = app.config['REDIS_HOST']
    redis_password = app.config['REDIS_PASSWORD']
    redis_port = app.config['REDIS_PORT']
    try:
        client = redis.Redis(host=redis_host, password=redis_password, port=redis_port, db=0,
                         socket_timeout=5,charset="utf-8", decode_responses=True
                         )
        ping = client.ping()
        if ping is True:
            app.logger.info("Redis connection registered")
            return client
    except Exception as e:
        app.logger.exception('REDIS ERROR: %s' % str(e))
        pass  # passing Redis exceptions since its not vital at this stage

def register_exceptions(blueprint, app):
    ce = CustomErrorHandlers(blueprint)
    ce.register_exceptions() # This registers custom exception error handlers into this blueprint
    app.logger.info("Registered custom exceptions")


def create_app() -> Flask:
    """FLask app creating factory"""
    application = Flask(__name__)
    CORS(application)
    #api = Api(application)
    application.config.from_object(config)
    register_exceptions(autoscaler_blueprint,application)
    application.register_blueprint(autoscaler_blueprint, url_prefix='/v1/autoscaler')
    application.redis = connect_redis(application)

    return application

def make_celery(app):
    # create context tasks in celery
    celery = Celery(
        app.import_name,
        # broker=app.config['BROKER_URL']
        broker="redis://redis:6379/0"
    )
    celery.conf.update(app.config)
    celery.config_from_object(celeryconfig)
    TaskBase = celery.Task

    class ContextTask(TaskBase):
        abstract = True

        def __call__(self, *args, **kwargs):
            with app.app_context():
                return TaskBase.__call__(self, *args, **kwargs)

    celery.Task = ContextTask
    return celery

application = create_app()
celery = make_celery(application)

if __name__ == '__main__':
    application = create_app()
    application.run(debug=True, port=5001, host='0.0.0.0')
