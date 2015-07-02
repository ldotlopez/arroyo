from ldotcommons import utils

import arroyo.exc
from arroyo import (
    exts,
    models
)


class DownloadCommand(exts.Command):
    help = 'manage downloads'

    arguments = (
        exts.argument(
            '-l', '--list',
            dest='show',
            action='store_true',
            help='show current downloads'),

        exts.argument(
            '-a', '--add',
            dest='add',
            help='download a source ID'),

        exts.argument(
            '-r', '--remove',
            dest='remove',
            help='cancel (and/or remove) a source ID'),

        exts.argument(
            '-f', '--filter',
            dest='query',
            type=str,
            action=utils.DictAction,
            help='filters to apply in key_mod=value form'),

        exts.argument(
            '--queries',
            dest='from_queries',
            action='store_true',
            help="Download matching sources from queries"),

        exts.argument(
            '-n', '--dry-run',
            dest='dry_run',
            action='store_true',
            help='don\'t download matching sources, just show them')
    )

    def run(self, args):
        show = args.show
        source_id_add = args.add
        source_id_remove = args.remove
        query = args.query
        from_queries = args.from_queries
        dry_run = args.dry_run

        add, remove, source_id = False, False, False
        if source_id_add:
            add, source_id = True, source_id_add

        if source_id_remove:
            remove, source_id = True, source_id_remove

        if sum([1 for x in (show, add, remove, from_queries) if x]) > 1:
            msg = 'Only one action at time is supported'
            raise arroyo.exc.ArgumentError(msg)

        if show:
            for src in self.app.downloads.list():
                print(src.pretty_repr)

        elif source_id_add:
            src = self.app.db.get(models.Source, id=source_id)
            if not src:
                msg = "Source with id {id} not found"
                msg = msg.format(id=source_id)
                self.app.logger.error(msg)
                return

            self.app.downloads.add(src)

        elif source_id_remove:
            src = self.app.db.get(models.Source, id=source_id)
            if not src:
                msg = "Source with id {id} not found"
                msg = msg.format(id=source_id)
                self.app.logger.error(msg)
                return

            self.app.downloads.remove(src)

        elif query:
            spec = exts.QuerySpec('command-line', **query)
            srcs = self.app.selector.select(spec)
            for src in srcs:
                if not dry_run:
                    self.app.downloads.add(src)

                msg = "%s %s %s" % \
                    (src.pretty_repr, src.language, src.type)
                self.app.logger.info(msg)

        elif from_queries:
            specs = self.app.selector.get_queries_specs()
            for spec in specs:
                srcs = self.app.selector.selection(spec)
                if srcs is None:
                    msg = "No selection for {query}"
                    msg = msg.format(query=query)
                    self.app.logger.warning(msg)
                    continue

                self.app.logger.info(query)

                for src in srcs:
                    if not dry_run:
                        self.app.downloads.add(src)

                    msg = "%s %s %s" % \
                        (src.pretty_repr, src.language, src.type)
                    self.app.logger.info(msg)


__arroyo_extensions__ = [
    ('command', 'download', DownloadCommand)
]
