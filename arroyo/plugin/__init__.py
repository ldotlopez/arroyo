import abc


from arroyo import (
    exc,
    models
)
from arroyo.downloads import Downloader
from arroyo.importer import Origin
from arroyo.selector import (
    Filter,
    IterableFilter,
    Query,
    QuerySetFilter,
    Sorter
)
from appkit import application
from appkit.application import cliargument
from appkit.cron import Task


class Extension(application.Extension):
    def __init__(self, app, *args, **kwargs):
        super().__init__()
        self.app = app


class Command(application.Command, Extension):
    @abc.abstractmethod
    def execute(self, arguments):
        raise NotImplementedError


class Service(application.Service, Extension):
    def __init__(self, app):
        super().__init__()
        self.app = app


__all__ = [
    # Other modules
    'exc',
    'extension',
    'models',

    # Extensible classes
    'Command',
    'CronTask',
    'Downloader',
    'IterableFilter',
    'Origin',
    'Query',
    'QuerySetFilter',
    'Service',
    'Sorter',

    # Tools
    'cliargument'
]
