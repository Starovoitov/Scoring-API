import redis
import ast
import sys


class RedisStore:
    """Record format in redis: { account : {score: value, nclient1: [interests], nclient2: [interests]}}"""
    cache = {}

    def __init__(self, host='localhost', port=6379, db=0, max_cache_size=1000, retry_on_timeout=True,
                 socket_timeout=5, socket_keepalive=True):
        self.max_cache_size = max_cache_size
        self.db = redis.Redis(host=host, port=port, db=db, retry_on_timeout=retry_on_timeout,
                              socket_timeout=socket_timeout, socket_keepalive=socket_keepalive)
        self.destroy_store()

    def update_cache(self, key, data):
        if key not in self.cache:
            self.cache[key] = data
        else:
            updated_data = self.cache[key].copy()
            updated_data.update(data)
            self.cache[key] = updated_data
            if self.get_cache_size() >= self.max_cache_size:
                self.update_db()
                self.cache.clear()

    def update_db(self, **records):
        db_addition = records
        if not records:
            db_addition = self.cache
        for key, data in db_addition.iteritems():
            if not self.db.get(key):
                self.db.set(key, data)
            else:
                updated_data = self.convert_str_to_dict(self.db.get(key)).copy()
                updated_data.update(data)
                self.db.set(key, updated_data)
        return

    def get_cache(self):
        return self.cache

    def get_cache_size(self):
        return sys.getsizeof(self.cache)

    def cache_get(self, key):
        if key in self.cache:
            return self.cache[key]
        else:
            return

    def get(self, key):
        if self.db.get(key):
            return self.db.get(key)
        else:
            return

    def destroy_store(self):
        for key in self.db.scan_iter("*"):
            self.db.delete(key)

    @staticmethod
    def convert_str_to_dict(string):
        try:
            return ast.literal_eval(string)
        except ValueError:
            raise ValueError("Couldn't transform the string to dictionary")

    @classmethod
    def config_parser(cls, config):
        pass
