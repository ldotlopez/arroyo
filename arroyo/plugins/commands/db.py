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


import contextlib


import tqdm


models = pluginlib.models


@contextlib.contextmanager
def _mute_logger(logger):
    mute = 51
    prev = logger.getEffectiveLevel()
    logger.setLevel(mute)
    yield
    logger.setLevel(prev)


def _tqdm(*args, **kwargs):
    kwargs_ = dict(dynamic_ncols=True, disable=not sys.stderr.isatty())
    kwargs_.update(kwargs)

    return tqdm.tqdm(*args, **kwargs_)


class Command(pluginlib.Command):
    __extension_name__ = 'db'

    HELP = 'Manage database (for advanced users)'
    ARGUMENTS = (
        pluginlib.cliargument(
            '--archive',
            dest='archive_source_id',
            help='Sets downloading state to ARCHIVED on a sources',
        ),

        pluginlib.cliargument(
            '--archive-all',
            dest='archive_all',
            action='store_true',
            help='Sets downloading state to ARCHIVED on all sources'
        ),

        pluginlib.cliargument(
            '--shell',
            dest='shell',
            action='store_true',
            help=('Start an interactive python interpreter with database '
                  'access')
        ),

        pluginlib.cliargument(
            '--reset',
            dest='reset_source_id',
            help='Sets downloading state to NONE on a source'
        ),

        pluginlib.cliargument(
            '--reset-db',
            dest='reset',
            action='store_true',
            help='Empty database'
        ),

        pluginlib.cliargument(
            '--reset-states',
            dest='reset_states',
            action='store_true',
            help='Sets downloading state to NONE on all sources'
        ),

        pluginlib.cliargument(
            '--upgrade',
            dest='upgrade',
            action='store_true',
            help='Upgrade database content, *not* schema'
        )
    )

    def execute(self, app, arguments):
        db = app.db

        archive_all = arguments.archive_all
        archive_source_id = arguments.archive_source_id
        shell = arguments.shell
        reset = arguments.reset
        reset_states = arguments.reset_states
        reset_source_id = arguments.reset_source_id
        upgrade = arguments.upgrade

        all_ = [
            archive_all,
            archive_source_id,
            shell,
            reset,
            reset_source_id,
            reset_states,
            upgrade,
        ]
        test = [1 for x in all_ if x]

        if sum(test) == 0:
            msg = "No action specified"
            raise pluginlib.exc.ArgumentsError(msg)

        elif sum(test) > 1:
            msg = "Just one option can be specified at one time"
            raise pluginlib.exc.ArgumentsError(msg)

        if archive_all:
            db.update_all_states(models.State.ARCHIVED)

        elif archive_source_id or reset_source_id:
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

        elif reset:
            db.reset()

        elif reset_states:
            db.update_all_states(models.State.NONE)

        elif arguments.upgrade:
            self.migrations()

        else:
            # This code should never be reached but keeping it here we will
            # prevent future mistakes
            msg = "Incorrect usage"
            raise pluginlib.exc.ArgumentsError(msg)

    def migrations(self):
        migrations = [
            ('01_normalize-entities',
             self._migration_normalize_entities),

            ('02_delete-entities-with-zero-sources',
             self._migration_delete_entities_with_zero_sources),

            ('03_migration_delete_false_selections',
             self._migration_delete_false_selections)
        ]

        for (name, fn) in migrations:
            fullname = 'core.db.migration.' + name
            if not self.app.variables.get(fullname, False):
                fn()
                self.app.variables.set(fullname, True)

    def _migration_normalize_entities(self):
        sess = self.app.db.session

        qs = sess.query(models.Source)
        count = qs.count()

        msg = "Rebuilding entities"
        pbar = _tqdm(total=count, desc=msg)

        with _mute_logger(self.app.mediainfo.logger):
            self.app.mediainfo.logger.setLevel(51)

            for (idx, src) in enumerate(qs):
                if src.entity:
                    prev_entity = src.entity
                    prev_selection = src.entity.selection
                else:
                    prev_entity = None
                    prev_selection = None

                self.app.mediainfo.process(src)

                # Update previous selection if entity has changed
                if prev_selection and prev_entity != src.entity:
                    prev_selection.entity = src.entity

                pbar.update()

            sess.commit()

    def _migration_delete_entities_with_zero_sources(self):
        sess = self.app.db.session

        # EntitySupport
        for model in [models.Episode, models.Movie]:
            qs = sess.query(model)
            count = qs.count()

            msg = "Delete '{model}'s without sources"
            msg = msg.format(model=model.__name__)
            pbar = _tqdm(total=count, desc=msg)

            deleted = 0
            for (idx, entity) in enumerate(qs):
                source_count = entity.sources.count()
                if source_count == 0:
                    sess.delete(entity)
                    deleted += 1

                pbar.update()

            # qs = sess.query(model).filter(~model.sources.any())
            # count = qs.count()
            # qs.delete(synchronize_session=False)
            msg = "Deleted {count} '{model}'s"
            msg = msg.format(count=count, model=model.__name__)
            print(msg)

        sess.commit()

    def _migration_delete_false_selections(self):
        sess = self.app.db.session

        source_ids = [x.id for x in sess.query(models.Source)]

        # EntitySupport
        for model in [models.Episode, models.Movie]:
            msg = "Deleting false {model} selections from database"
            msg = msg.format(model=model.__name__)
            print(msg)

            sess.query(model.SELECTION_MODEL).filter(
                ~model.SELECTION_MODEL.source_id.in_(source_ids)
            ).delete(synchronize_session='fetch')

            entity_ids = [x.id for x in sess.query(model)]
            for selection in sess.query(model.SELECTION_MODEL):
                if (selection.entity is None or
                        selection.entity.id not in entity_ids):
                    sess.delete(selection)

        sess.commit()


__arroyo_extensions__ = [
    Command
]
