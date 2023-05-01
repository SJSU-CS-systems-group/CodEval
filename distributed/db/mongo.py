import pymongo
import click
from configparser import ConfigParser
from .ConnectionException import DBConnectionException


class MongoConnection(object):
    _client = None
    _parser = None

    def __new__(cls):
        if not hasattr(cls, 'instance'):
            cls.instance = super(MongoConnection, cls).__new__(cls)
            cls.instance._connect()
        return cls.instance

    def _get_parser(self):
        if self._parser is None:
            self._parser = ConfigParser()
            self._parser.read(click.get_app_dir('codeval.ini'))
            if not self._parser.has_section('MONGO') or \
                not self._parser.has_option('MONGO', 'url') or \
                not self._parser.has_option('MONGO', 'db'):
                raise DBConnectionException("MongoDB configuration not found")
        return self._parser

    def _connect(self):
        url = self._get_parser()['MONGO']['url']
        try:
            self._client = pymongo.MongoClient(
                host=url, serverSelectionTimeoutMS=5000)
            self._client.server_info()  # force connect on first query
        except pymongo.errors.ServerSelectionTimeoutError:
            raise DBConnectionException("Could not connect to MongoDB")

    def get_client(self):
        return self._client
    
    def get_db(self):
        return self._client[self._get_parser()['MONGO']['db']]
