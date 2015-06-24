from ldotcommons import utils

from arroyo import (
    exc,
    exts,
    models,
    selector
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
        dry_run = args.dry_run

        add, remove, source_id = False, False, False
        if source_id_add:
            add, source_id = True, source_id_add

        if source_id_remove:
            remove, source_id = True, source_id_remove

        if sum([1 for x in (show, add, remove, query) if x]) > 1:
            msg = 'Only one action at time is supported'
            raise exc.ArgumentError(msg)

        if show:
            for src in self.app.downloads.list():
                print(src.pretty_repr)

        elif source_id_add:
            src = self.app.db.get(models.Source, id=source_id)
            self.app.downloads.add(src)

        elif source_id_remove:
            src = self.app.db.get(models.Source, id=source_id)
            self.app.downloads.remove(src)

        else:
            if not query:
                queries = self.app.downloads.get_queries()
            else:
                queries = {'Command line': selector.Query(**query)}

            for (name, query) in queries.items():
                print(name)
                srcs = self.app.selector.select(query, everything=False)
                for src in srcs:
                    if not dry_run:
                        self.app.downloads.add(src)
                    print(src.pretty_repr)


__arroyo_extensions__ = [
    ('command', 'download', DownloadCommand)
]
