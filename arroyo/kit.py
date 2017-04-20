# -*- coding: utf-8 -*-

# Copyright (C) 2015 Luis López <luis@cuarentaydos.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301,
# USA.


import argparse


from appkit import application
from appkit.application import (
    commands,
    cron,
    services
)


# class Requirements(enum.Enum):
#     APPLICATION = 'application'
#     # DATABASE = 'database'
#     # NETWORK = 'network'
#     SETTINGS = 'settings'
#     VARIABLES = 'variables'


class Extension(application.Extension):
    def __init__(self, app, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.app = app

    # def __init__(self, settings, variables, *args, **kwargs):
    #     super().__init__(*args, **kwargs)
    #     self.settings = settings
    #     self.variables = variables
    #
    # @classmethod
    # def requirements(cls):
    #     return [Requirements.SETTINGS, Requirements.VARIABLES]


class Task(cron.Task, Extension):
    pass


class Command(commands.Command, Extension):
    pass


class CommandManager(commands.Manager):
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
            '--auto-cron',
            default=None,
            action='store_true',
            dest='auto-cron')

        return parser


class CronManager(cron.Manager):
    TASK_EXTENSION_POINT = Task

    def load_checkpoint(self, task):
        return self.app.variables.get(
            'cron.states.{name}'.format(name=task.__extension_name__),
            default={})

    def save_checkpoint(self, task, checkpoint):
        self.app.variables.set(
            'cron.states.{name}'.format(name=task.__extension_name__),
            checkpoint)


class Service(services.Service, Extension):
    pass


class Application(application.BaseApplication):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._extension_deps_registry = {}

    # def register_extension_point(self, extension_point):
    #     ret = super().register_extension_point(extension_point)

    #     meth = getattr(extension_point, 'requirements', None)
    #     if meth and callable(meth):
    #         self._extension_deps_registry[extension_point] = meth()

    #     return ret

    def get_extension(self, extension_point, name, *args, **kwargs):
        # reqs = self._extension_deps_registry.get(extension_point, [])

        # ifaces = []
        # for req in reqs:
        #     if req == Requirements.APPLICATION:
        #         ifaces.append(self)

        #     elif req == Requirements.SETTINGS:
        #         ifaces.append(self.settings)

        #     elif req == Requirements.VARIABLES:
        #         ifaces.append(self.variables)

        #     else:
        #         raise NotImplementedError(req)

        # args = ifaces + list(args)

        return super().get_extension(extension_point, name,
                                     self, *args, **kwargs)
