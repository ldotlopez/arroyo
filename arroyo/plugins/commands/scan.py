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


from appkit import logging


class ScanCommand(pluginlib.Command):
    __extension_name__ = 'scan'

    HELP = 'Scan sources (i.e. websites)'
    ARGUMENTS = (
        pluginlib.cliargument(
            '--provider',
            dest='provider',
            type=str,
            help='Provider to use'),
        pluginlib.cliargument(
            '-u', '--uri',
            dest='uri',
            type=str,
            default=None,
            help='Base URI to scan'),
        pluginlib.cliargument(
            '-i', '--iterations',
            dest='iterations',
            type=int,
            default=1,
            help=('Iterations to run over base URI (Think about pages in a '
                  'website)')),
        pluginlib.cliargument(
            '-t', '--type',
            dest='type',
            type=str,
            help='Override type of found sources'),
        pluginlib.cliargument(
            '-l', '--language',
            dest='language',
            type=str,
            help='Override language of found sources'),
        pluginlib.cliargument(
            '--from-config',
            dest='from_config',
            action='store_true',
            default=False,
            help='Import from the origins defined in the configuration file')
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger('scan')

    def execute(self, app, arguments):
        importer = app.importer

        if arguments.from_config and arguments.provider:
            msg = ("Only one of --from-config or --provider options can be "
                   "specified. They are mutually exclusive.")
            raise pluginlib.exc.ArgumentsError(msg)

        if arguments.provider or arguments.uri:
            # Build origin data
            keys = [
                ('provider', str),
                ('uri', str),
                ('iterations', int),
                ('type', str),
                ('language', str)
            ]

            origin_data = {}
            for (k, t) in keys:
                v = getattr(arguments, k, None)

                if v is not None:
                    try:
                        v = t(v)
                    except ValueError:
                        msg = 'Invalid argument {key}'
                        msg = msg.format(key=k)
                        self.logger.error(msg)
                        continue

                    origin_data[k] = v

            origin = importer.origin_from_params(**origin_data)
            importer.process(origin)

        elif arguments.from_config:
            importer.run()

        else:
            # This code should never be reached but keeping it here we will
            # prevent future mistakes
            msg = "Incorrect usage"
            raise pluginlib.exc.ArgumentsError(msg)


__arroyo_extensions__ = [
    ScanCommand
]
