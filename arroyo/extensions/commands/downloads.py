from ldotcommons import utils


from arroyo.app import app, argument
from arroyo import models, selector
import arroyo.exc


@app.register('command', 'downloads')
class DownloadsCommand:
    help = 'Show and manage downloads'
    arguments = (
        argument(
            '-l', '--list',
            dest='show',
            action='store_true',
            help='Show current downloads'),

        argument(
            '-a', '--add',
            dest='add',
            help='Download a source ID'),

        argument(
            '-r', '--remove',
            dest='remove',
            help='Cancel (and/or remove) a source ID'),

        argument(
            '-f', '--filter',
            dest='filters',
            type=str,
            action=utils.DictAction,
            help='Filters to apply in key_mod=value form'),

        argument(
            '-n', '--dry-run',
            dest='dry_run',
            action='store_true',
            help='Push found sources to downloader.')
    )

    def run(self):
        show = app.arguments.show
        source_id_add = app.arguments.add
        source_id_remove = app.arguments.remove
        filters = app.arguments.filters
        dry_run = app.arguments.dry_run

        add, remove, source_id = False, False, False
        if source_id_add:
            add, source_id = True, source_id_add

        if source_id_remove:
            remove, source_id = True, source_id_remove

        if not any([show, add, remove, filters]):
            raise arroyo.exc.ArgumentError('No action specified')

        if sum([1 for x in (show, add, remove, filters) if x]) > 1:
            msg = 'Only one action at time is supported'
            raise arroyo.exc.ArgumentError(msg)

        if show:
            for src in app.downloader.list():
                print(src.pretty_repr)

        elif source_id_add:
            src = app.db.get(models.Source, id=source_id_add)
            app.downloader.add(src)

        elif source_id_remove:
            src = app.db.get(models.Source, id=source_id_remove)
            app.downloader.remove(src)

        elif filters:
            srcs = app.selector.select(selector.Query(**filters))
            for src in srcs:
                print(src.pretty_repr)

        return

        # Downloader control
        if any([show, add, remove]):
            downloads(show=show, add=add, remove=remove, source_id=source_id)

        # Source selection
        elif filters:
            print(repr(filters))

            if 'series' in filters:
                sync()
                download_episodes(**filters)
            elif 'movie' in filters:
                sync()
                download_movies(**filters)

            # Download sources
            else:
                sync()
                sources = query(filters)
                for src in sources:
                    print(source_repr(src))
                    if not dry_run:
                        app.downloader.add(src)