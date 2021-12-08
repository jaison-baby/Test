from flask import jsonify, current_app as app, Blueprint


class APIBaseError(Exception):
    """ Base class for custom web API exceptions which registered into
    flask error handler https://flask.palletsprojects.com/en/1.1.x/patterns/apierrors/
    https://instructobit.com/tutorial/112/Python-Flask%3A-error-and-exception-handling
    """
    def __init__(self, message: str, status_code: int = None, payload: str = None, original_exception: Exception = None):
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload
        self.original_exception = original_exception

class APIError(APIBaseError):
    """
    Custom Authentication Error Class.
    Now its just used for proof of concept, not used anywhere
    """
    code = 403
    description = "Authentication Error"

class RedisError(APIBaseError):
    """ Custom Exception for Redis related exceptions """
    code = 400
    description = "Redis Error"

class ConcsulError(APIBaseError):
    code = 400
    description  = "Consul Error"

class AWSerror(APIBaseError):
    code = 400
    description  = "AWS API Error"

class ParameterError(APIBaseError):
    code = 400
    description  = "check parameter"

class DatabaseError(APIBaseError):
    code = 400
    description  = "Database Error"

class CustomErrorHandlers(object):
    """ class that handles registration of custom exceptions into Flask blueprint
    https://stackoverflow.com/questions/58728366/python-flask-error-handling-with-blueprints
    """
    def __init__(self, blueprint: Blueprint):
        self.bp = blueprint

    def register_exceptions(self):
        """iterating over all subclasses of main Exception class APIBaseError and register that into
        flask app blueprint"""
        for cls in APIBaseError.__subclasses__():
            self.bp.app_errorhandler(cls)(handle_exception)

def handle_exception(err: Exception):
    """Return custom JSON when APIError or its children are raised"""
    response = {"error": err.description, "message": err.message, "code": err.code}
    # Add some logging so that we can monitor different types of exceptions in logs
    app.logger.exception( 'Description: {} Message: {} Original_exception: {}'.format(err.description, err.message, str(err.original_exception)))
    return jsonify(response), err.code


class BaseError(Exception):
    """ Base class for non-web API exceptions for, example celery tasks"""
    def __init__(self, message: str, original_exception: Exception = None):
        self.message = message
        self.original_exception = original_exception

class PrometheusError(BaseError):
    pass

class SlackError(BaseError):
    pass