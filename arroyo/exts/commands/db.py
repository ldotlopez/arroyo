from arroyo import (
    exc,
    exts,
    models
)


class DbCommand(exts.Command):
    help = 'Database commands'
    arguments = (
        exts.argument(
            '--shell',
            dest='shell',
            action='store_true',
            help=('Start a interactive python interpreter in the db '
                  'environment')),

        exts.argument(
            '--reset-db',
            dest='reset',
            action='store_true',
            help='Empty db'),

        exts.argument(
            '--reset-states',
            dest='reset_states',
            action='store_true',
            help='Sets state to NONE on all sources'),

        exts.argument(
            '--archive-all',
            dest='archive_all',
            action='store_true',
            help='Sets state to ARCHIVED on all sources'),

        exts.argument(
            '--reset',
            dest='reset_source_id',
            help='Reset state of a source'),

        exts.argument(
            '--archive',
            dest='archive_source_id',
            help='Archive a source')
        )

    def run(self):
        var_args = vars(self.app.arguments)
        keys = ('shell reset_db reset_states archive_all '
                'reset_source_id archive_source_id').split()
        opts = {k: var_args.get(k) for k in keys}

        shell = opts.get('shell')
        reset = opts.get('reset')
        reset_states = opts.get('reset_states')
        archive_all = opts.get('archive_all')
        reset_source_id = opts.get('reset_source_id')
        archive_source_id = opts.get('archive_source_id')
        reset = opts.get('reset')

        test = [1 for x in (reset, shell, reset_states, archive_all,
                            reset_source_id, archive_source_id) if x]

        if sum(test) == 0:
            raise exc.ArgumentError('No action specified')

        elif sum(test) > 1:
            msg = 'Just one option can be specified at one time'
            raise exc.ArgumentError(msg)

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
                raise exc.ArgumentError(msg)

            source.state = state
            self.app.db.session.commit()

__arroyo_extensions__ = [
    ('command', 'db', DbCommand)
]
