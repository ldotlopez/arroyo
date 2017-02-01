# -*- coding: utf-8 -*-

import abc
import argparse
import warnings


from appkit import application
from appkit.application import (
    commands,
    cron
)


from arroyo import models


class Extension(application.Extension):
    def __init__(self, app, *args, **kwargs):
        super().__init__()
        self.app = app


class Command(commands.Command, Extension):
    """
    Custom Command to alter:
    - Custom execute method (bypasses application argument since it's in base
      Extension)
    """
    @abc.abstractmethod
    def execute(self, arguments):
        raise NotImplementedError()


class Task(cron.Task, Extension):
    pass


class CommandManager(commands.CommandManager):
    """
    Custom CommandManager to alter:
    - Own Command extension (Different signature)
    - Custom execute_command_extension to handle custom signature
    - Own base argument parser
    """

    COMMAND_EXTENSION_POINT = Command

    @classmethod
    def build_base_argument_parser(cls):
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument(
            '-h', '--help',
            action='store_true',
            dest='help')

        parser.add_argument(
            '-v', '--verbose',
            dest='verbose',
            default=0,
            action='count')

        parser.add_argument(
            '-q', '--quiet',
            dest='quiet',
            default=0,
            action='count')

        parser.add_argument(
            '-c', '--config-file',
            dest='config-files',
            action='append',
            default=[])

        parser.add_argument(
            '--plugin',
            dest='plugins',
            action='append',
            default=[])

        parser.add_argument(
            '--db-uri',
            dest='db-uri')

        parser.add_argument(
            '--downloader',
            dest='downloader')

        parser.add_argument(
            '--auto-import',
            default=None,
            action='store_true',
            dest='auto-import')

        parser.add_argument(
            '--auto-cron',
            default=None,
            action='store_true',
            dest='auto-cron')

        return parser

    def call_execute_method(self, command, arguments):
        return command.execute(arguments)


class CronManager(cron.CronManager):
    TASK_EXTENSION_POINT = Task

    def load_checkpoint(self, task):
        return self.app.variables.get(
            'cron.states.{name}'.format(name=task.__extension_name__),
            default={})

    def save_checkpoint(self, task, checkpoint):
        self.app.variables.set(
            'cron.states.{name}'.format(name=task.__extension_name__),
            checkpoint)

    def call_execute_method(self, task, app):
        return task.execute()


class Application(application.BaseApplication):
    def get_extension(self, extension_point, name, *args, **kwargs):
        return super().get_extension(extension_point, name, self,
                                     *args, **kwargs)
