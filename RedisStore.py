import redis
import ast
import sys


def check_availability(call_redis):
    """wrapper to decorate db operations with attempts to reconnect and death in case of failure"""
    def wrapper(self, *args, **kwargs):
        while self.attempt < self.retries:
            try:
                function_value = call_redis(self, *args, **kwargs)
                self.attempt = 0
                return function_value
            except redis.exceptions.ConnectionError:
                self.attempt += 1
                if self.attempt > self.retries:
                    self.logging.info("Redis is unavailable - stop using it")
                    return wrapper
                continue
    return wrapper


class RedisStore:
    """Record format in redis: { account : {score: value, nclient1: [interests], nclient2: [interests]}}"""
    cache = {}
    attempt = 0

    def __init__(self, host='localhost', port=6379, db=0, max_cache_size=1000, retry_on_timeout=True,
                 socket_timeout=5, socket_keepalive=True, retries=3, db_config=None, logger=None):
        if db_config:
            config_options = self.parse_config(db_config)
            host = config_options["host"]
            port = int(config_options["port"])
            db = int(config_options["db"])
            max_cache_size = int(config_options["max_cache_size"])
            retry_on_timeout = bool(config_options["retry_on_timeout"])
            socket_timeout = int(config_options["socket_timeout"])
            socket_keepalive = bool(config_options["socket_keepalive"])
            retries = int(config_options["retries"])

        self.db = redis.Redis(host=host, port=port, db=db, retry_on_timeout=retry_on_timeout,
                              socket_timeout=socket_timeout, socket_keepalive=socket_keepalive)

        if logger:
            self.logging = logger

        self.max_cache_size = max_cache_size
        self.retries = retries
        self.destroy_store()

    def update_cache(self, key, data):
        """records taking space lesser than max_cache_size are stored in memory cache"""
        if key not in self.cache:
            self.cache[key] = data
        else:
            updated_data = self.cache[key].copy()
            updated_data.update(data)
            self.cache[key] = updated_data

            if self.get_cache_size() >= self.max_cache_size and self.attempt <= self.retries:
                self.logging.info("Cache if full, it's content is flushed into db")
                self.flush_cache()

    def flush_cache(self):
        self.update_db()
        self.cache.clear()

    @check_availability
    def update_db(self, **records):
        """either writes given records in db or take it from cache"""
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
        self.logging.info("Database is updated")

    def get_cache(self):
        return self.cache

    def get_cache_size(self):
        return sys.getsizeof(self.cache)

    def cache_get(self, key):
        if key in self.cache:
            return self.cache[key]
        else:
            return

    @check_availability
    def get(self, key):
        if self.db.get(key):
            return self.db.get(key)
        else:
            return

    @check_availability
    def destroy_store(self):
        for key in self.db.scan_iter("*"):
            self.db.delete(key)

    @staticmethod
    def convert_str_to_dict(string):
        try:
            return ast.literal_eval(string)
        except ValueError:
            raise ValueError("Couldn't transform the string to dictionary")

    @staticmethod
    def parse_config(config):
        """config is expected to have 'option=value' format"""
        config_parameters = {}
        options = RedisStore.read_config(config)
        for option in options:
            option_name, option_value = option.split("=")
            config_parameters[option_name] = option_value

        return config_parameters

    @staticmethod
    def read_config(config):
        with open(config, 'r') as f:
            options = f.readlines()
        f.close()
        return [x.strip() for x in options]
