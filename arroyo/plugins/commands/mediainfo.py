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


models = pluginlib.models


class MediainfoCommand(pluginlib.Command):
    __extension_name__ = 'mediainfo'

    HELP = 'Extract media info from sources (for advanced users)'
    ARGUMENTS = (
        pluginlib.cliargument(
            '-i', '--item',
            dest='item',
            help='Extract (and override) media info from the selected source'
        ),
        pluginlib.cliargument(
            '-a', '--all',
            action='store_true',
            dest='all',
            help=('Extract (and override) media info from all sources in the '
                  'database')
        ),
    )

    def execute(self, app, arguments):
        db = app.db
        mediainfo = app.mediainfo

        item = arguments.item
        all_ = arguments.all

        test = sum([1 for x in [item, all_] if x])
        if test == 0:
            msg = "One of --item or --all options must be used"
            raise pluginlib.exc.ArgumentsError(msg)

        elif test > 1:
            msg = ("Only one of '--item' or '--all' options can be "
                   "specified. They are mutually exclusive.")
            raise pluginlib.exc.ArgumentsError(msg)

        if item:
            src = db.get(models.Source, id=item)
            if not src:
                msg = "No matching source with ID={id}"
                msg = msg.format(id=item)
                raise pluginlib.exc.ArgumentsError(msg)

            srcs = [src]

        elif all_:
            srcs = db.session.query(models.Source)

        mediainfo.process(*srcs)
        self.app.db.session.commit()


__arroyo_extensions__ = [
    MediainfoCommand
]
