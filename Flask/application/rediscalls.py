import redis
from flask import Flask
from datetime import timedelta
from exceptions import RedisError

class RedisConnection(object):
    """
    Class that handles getting and putting data into Redis key value store
    """
    def __init__(self, app: Flask):
        self.rds = app.redis

    def get_from_cache(self, key: str) -> str:
        """Data from redis."""
        try:
            val = self.rds.get(key)
            return val
        except Exception as e:
            raise RedisError('Redis connection exception', original_exception=e)

    def set_to_cache(self, key: str, value: str, ttl: int = None) -> bool:
        """Data to redis."""
        try:
            state = self.rds.setex(key, timedelta(seconds=ttl), value=value)
            return state
        except Exception as e:
            raise RedisError('Redis connection exception', original_exception=e)

 
