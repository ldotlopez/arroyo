# -*- coding: utf-8 -*-

from arroyo import plugin
models = plugin.models


class Command(plugin.Command):
    help = 'manage database'

    arguments = (
        plugin.argument(
            '--shell',
            dest='shell',
            action='store_true',
            help=('start a interactive python interpreter in the db '
                  'environment')),

        plugin.argument(
            '--reset-db',
            dest='reset',
            action='store_true',
            help='empty db'),

        plugin.argument(
            '--reset-states',
            dest='reset_states',
            action='store_true',
            help='sets state to NONE on all sources'),

        plugin.argument(
            '--archive-all',
            dest='archive_all',
            action='store_true',
            help='sets state to ARCHIVED on all sources'),

        plugin.argument(
            '--reset',
            dest='reset_source_id',
            help='reset state of a source'),

        plugin.argument(
            '--archive',
            dest='archive_source_id',
            help='archive a source')
        )

    def run(self, args):
        shell = args.shell
        reset = args.reset
        reset_states = args.reset_states
        archive_all = args.archive_all
        reset_source_id = args.reset_source_id
        archive_source_id = args.archive_source_id
        reset = args.reset

        test = [1 for x in (reset, shell, reset_states, archive_all,
                            reset_source_id, archive_source_id) if x]

        msg = None
        if sum(test) == 0:
            msg = "No action specified"
        elif sum(test) > 1:
            msg = "Just one option can be specified at one time"

        if msg:
            raise plugin.exc.PluginArgumentError(msg)

        if reset:
            self.app.db.reset()

        if reset_states:
            self.app.db.update_all_states(models.Source.State.NONE)

        if archive_all:
            self.app.db.update_all_states(models.Source.State.ARCHIVED)

        if shell:
            self.app.db.shell()

        source_id = reset_source_id or archive_source_id
        if source_id:
            if reset_source_id:
                state = models.Source.State.NONE
            else:
                state = models.Source.State.ARCHIVED

            source = self.app.db.get(models.Source, id=source_id)
            if not source:
                msg = "No source with ID={id}".format(id=source_id)
                raise plugin.exc.PluginArgumentError(msg)

            source.state = state
            self.app.db.session.commit()
            return

        msg = "Incorrect usage"
        raise plugin.exc.PluginArgumentError(msg)

__arroyo_extensions__ = [
    ('db', Command)
]
