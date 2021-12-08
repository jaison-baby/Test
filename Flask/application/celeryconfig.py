from celery.schedules import crontab


CELERY_IMPORTS = ('tasks.connection_request','tasks.load_request','tasks.update_cron')
CELERY_TASK_RESULT_EXPIRES = 30
CELERY_TIMEZONE = 'UTC'

CELERY_ACCEPT_CONTENT = ['json', 'msgpack', 'yaml']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'

CELERYBEAT_SCHEDULE = {
    'connection-request': {
        'task': 'tasks.connection_request.connectionRequest',
        'schedule': 3
    },
    'load-request': {
        'task': 'tasks.load_request.loadRequest',
        'schedule':5
    },
    'update-request':{
    	'task':'tasks.update_cron.updateInstanceMetric',
        'schedule': 2
    }
}