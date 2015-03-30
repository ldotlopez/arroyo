from ldotcommons import utils


from arroyo import (
    exc,
    exts,
    models,
    selector
)


class DownloadCommand(exts.Command):
    help = 'Show and manage downloads'
    arguments = (
        exts.argument(
            '-l', '--list',
            dest='show',
            action='store_true',
            help='Show current downloads'),

        exts.argument(
            '-a', '--add',
            dest='add',
            help='Download a source ID'),

        exts.argument(
            '-r', '--remove',
            dest='remove',
            help='Cancel (and/or remove) a source ID'),

        exts.argument(
            '-f', '--filter',
            dest='query',
            type=str,
            action=utils.DictAction,
            help='Filters to apply in key_mod=value form'),

        exts.argument(
            '-n', '--dry-run',
            dest='dry_run',
            action='store_true',
            help='Push found sources to downloader.')
    )

    def run(self):
        show = self.app.arguments.show
        source_id_add = self.app.arguments.add
        source_id_remove = self.app.arguments.remove
        query = self.app.arguments.query
        dry_run = self.app.arguments.dry_run

        add, remove, source_id = False, False, False
        if source_id_add:
            add, source_id = True, source_id_add

        if source_id_remove:
            remove, source_id = True, source_id_remove

        if sum([1 for x in (show, add, remove, query) if x]) > 1:
            msg = 'Only one action at time is supported'
            raise exc.ArgumentError(msg)

        if show:
            for src in self.app.downloader.list():
                print(src.pretty_repr)

        elif source_id_add:
            src = self.app.db.get(models.Source, id=source_id)
            self.app.downloader.add(src)

        elif source_id_remove:
            src = self.app.db.get(models.Source, id=source_id)
            self.app.downloader.remove(src)

        else:
            if not query:
                queries = self.app.downloader.get_queries()
            else:
                queries = {'Command line': query}

            # self.app.selector.multiselect({
            #     k: selector.Query(v) for (k, v) in queries.items()
            # })
            for (name, filters) in queries.items():
                print(name)
                srcs = self.app.selector.select(selector.Query(**filters))
                for src in srcs:
                    if not dry_run:
                        self.app.downloader.add(src)
                    print(src.pretty_repr)


__arroyo_extensions__ = [
    ('command', 'download', DownloadCommand)
]
