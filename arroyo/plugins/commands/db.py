# -*- coding: utf-8 -*-

from arroyo import pluginlib
models = pluginlib.models


class Command(pluginlib.Command):
    __extension_name__ = 'db'

    HELP = 'manage database'
    ARGUMENTS = (
        pluginlib.cliargument(
            '--shell',
            dest='shell',
            action='store_true',
            help=('start a interactive python interpreter in the db '
                  'environment')),

        pluginlib.cliargument(
            '--reset-db',
            dest='reset',
            action='store_true',
            help='empty db'),

        pluginlib.cliargument(
            '--reset-states',
            dest='reset_states',
            action='store_true',
            help='sets state to NONE on all sources'),

        pluginlib.cliargument(
            '--archive-all',
            dest='archive_all',
            action='store_true',
            help='sets state to ARCHIVED on all sources'),

        pluginlib.cliargument(
            '--reset',
            dest='reset_source_id',
            help='reset state of a source'),

        pluginlib.cliargument(
            '--archive',
            dest='archive_source_id',
            help='archive a source')
        )

    def execute(self, args):
        shell = args.shell
        reset = args.reset
        reset_states = args.reset_states
        archive_all = args.archive_all
        reset_source_id = args.reset_source_id
        archive_source_id = args.archive_source_id
        reset = args.reset

        test = [1 for x in (reset, shell, reset_states, archive_all,
                            reset_source_id, archive_source_id) if x]

        if sum(test) == 0:
            msg = "No action specified"
            raise pluginlib.exc.ArgumentsError(msg)

        elif sum(test) > 1:
            msg = "Just one option can be specified at one time"
            raise pluginlib.exc.ArgumentsError(msg)

        if reset:
            self.app.db.reset()

        elif reset_states:
            self.app.db.update_all_states(models.Source.State.NONE)

        elif archive_all:
            self.app.db.update_all_states(models.Source.State.ARCHIVED)

        elif shell:
            sess = self.app.db.session
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
                state = models.Source.State.NONE
            else:
                state = models.Source.State.ARCHIVED

            source = self.app.db.get(models.Source, id=source_id)
            if not source:
                msg = "No source with ID={id}".format(id=source_id)
                raise pluginlib.exc.ArgumentsError(msg)

            source.state = state
            self.app.db.session.commit()

        else:
            # This code should never be reached but keeping it here we will
            # prevent future mistakes
            msg = "Incorrect usage"
            raise pluginlib.exc.ArgumentsError(msg)


__arroyo_extensions__ = [
    Command
]
