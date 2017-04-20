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


class Command(pluginlib.Command):
    __extension_name__ = 'db'

    HELP = 'Manage database (for advanced users)'
    ARGUMENTS = (
        pluginlib.cliargument(
            '--shell',
            dest='shell',
            action='store_true',
            help=('Start an interactive python interpreter with database '
                  'access')),

        pluginlib.cliargument(
            '--reset-db',
            dest='reset',
            action='store_true',
            help='Empty database'),

        pluginlib.cliargument(
            '--reset-states',
            dest='reset_states',
            action='store_true',
            help='Sets downloading state to NONE on all sources'),

        pluginlib.cliargument(
            '--archive-all',
            dest='archive_all',
            action='store_true',
            help='Sets downloading state to ARCHIVED on all sources'),

        pluginlib.cliargument(
            '--reset',
            dest='reset_source_id',
            help='Sets downloading state to NONE on a source'),

        pluginlib.cliargument(
            '--archive',
            dest='archive_source_id',
            help='Sets downloading state to ARCHIVED on a sources'),
        )

    def execute(self, app, arguments):
        db = app.db

        shell = arguments.shell
        reset = arguments.reset
        reset_states = arguments.reset_states
        archive_all = arguments.archive_all
        reset_source_id = arguments.reset_source_id
        archive_source_id = arguments.archive_source_id
        reset = arguments.reset

        test = [1 for x in (reset, shell, reset_states, archive_all,
                            reset_source_id, archive_source_id) if x]

        if sum(test) == 0:
            msg = "No action specified"
            raise pluginlib.exc.ArgumentsError(msg)

        elif sum(test) > 1:
            msg = "Just one option can be specified at one time"
            raise pluginlib.exc.ArgumentsError(msg)

        if reset:
            db.reset()

        elif reset_states:
            db.update_all_states(models.State.NONE)

        elif archive_all:
            db.update_all_states(models.State.ARCHIVED)

        elif shell:
            sess = db.session
            print("[!!] Database connection in 'sess' {}".format(sess))
            print("[!!] If you make any changes remember to call "
                  "sess.commit()")
            try:
                import ipdb
            except ImportError:
                import pdb
                ipdb = pdb
            ipdb.set_trace()

        elif reset_source_id or archive_source_id:
            source_id = reset_source_id or archive_source_id

            if reset_source_id:
                state = models.State.NONE
            else:
                state = models.State.ARCHIVED

            source = db.get(models.Source, id=source_id)
            if not source:
                msg = "No source with ID={id}".format(id=source_id)
                raise pluginlib.exc.ArgumentsError(msg)

            source.state = state
            db.session.commit()

        else:
            # This code should never be reached but keeping it here we will
            # prevent future mistakes
            msg = "Incorrect usage"
            raise pluginlib.exc.ArgumentsError(msg)


__arroyo_extensions__ = [
    Command
]
