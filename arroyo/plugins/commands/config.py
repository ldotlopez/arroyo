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


from arroyo import pluginlib


import sys
import yaml


from appkit import loggertools


class ConfigCommand(pluginlib.Command):
    __extension_name__ = 'config'

    HELP = 'Manage configuration (for advanced users)'

    def setup_argparser(cls, cmdargparser):
        cls.opparser = cmdargparser.add_subparsers(dest='operation')

        cls.setparser = cls.opparser.add_parser('set')
        cls.setparser.add_argument('-t', '--type', dest='type')
        cls.setparser.add_argument('key', nargs=1)
        cls.setparser.add_argument('value', nargs=1)

        cls.getparser = cls.opparser.add_parser('get')
        cls.getparser.add_argument('key', nargs=1)

        cls.delparser = cls.opparser.add_parser('delete')
        cls.delparser.add_argument('key', nargs=1)

        cls.dumpparser = cls.opparser.add_parser('dump')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = loggertools.getLogger('config')

    def execute(self, app, arguments):
        types_map = {
            None: yaml.load,
            'int': int,
            'bool': bool,
            'str': str,
            'float': float,
            'dict': yaml.load,
            'list': yaml.load
        }

        settings = app.settings

        if arguments.operation == 'dump':
            settings.dump(sys.stdout)

        elif arguments.operation == 'set':
            if arguments.type not in types_map:
                msg = "Unknow type '{type}'"
                msg = msg.format(type=arguments.type)
                self.logger.error(msg)
                return

            settings.set(
                arguments.key[0],
                types_map[arguments.type](arguments.value[0]))

            cfgfile = vars(arguments)['config-files'][-1]
            with open(cfgfile, 'w') as fh:
                settings.write(fh)

        elif arguments.operation == 'get':
            print(yaml.dump(settings.get(arguments.key[0])))

__arroyo_extensions__ = [
    ConfigCommand
]
