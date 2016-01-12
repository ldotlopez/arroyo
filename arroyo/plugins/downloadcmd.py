# -*- coding: utf-8 -*-

from arroyo import plugin
models = plugin.models


from ldotcommons import utils


class DownloadCommand(plugin.Command):
    help = 'manage downloads'

    arguments = (
        plugin.argument(
            '-l', '--list',
            dest='show',
            action='store_true',
            help='show current downloads'),

        plugin.argument(
            '-a', '--add',
            dest='add',
            help='download a source ID'),

        plugin.argument(
            '-r', '--remove',
            dest='remove',
            help='cancel (and/or remove) a source ID'),

        plugin.argument(
            '-f', '--filter',
            dest='query',
            type=str,
            action=utils.DictAction,
            help='filters to apply in key_mod=value form'),

        plugin.argument(
            '--from-config',
            dest='from_config',
            action='store_true',
            help="Download matching sources from queries defined in config"),

        plugin.argument(
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
        from_config = args.from_config
        dry_run = args.dry_run

        add, remove, source_id = False, False, False
        if source_id_add:
            add, source_id = True, source_id_add

        if source_id_remove:
            remove, source_id = True, source_id_remove

        test = sum([1 for x in (show, add, remove, from_config) if x])

        if test == 0:
            msg = "No action specified"
            raise plugin.exc.PluginArgumentError(msg)

        elif test > 1:
            msg = "Only one action at time is supported"
            raise plugin.exc.PluginArgumentError(msg)

        if show:
            for src in self.app.downloads.list():
                self.app.logger.info(str(src))

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
            spec = plugin.QuerySpec('command-line', **query)
            matches = self.app.selector.matches(spec)
            srcs = self.app.selector.select(matches)
            for src in srcs:
                if not dry_run:
                    self.app.downloads.add(src)

                print(str(src))

        elif from_config:
            specs = self.app.selector.get_queries_specs()
            for spec in specs:
                matches = self.app.selector.matches(spec)
                srcs = self.app.selector.select(matches)
                if srcs is None:
                    msg = "No selection for {query}"
                    msg = msg.format(query=query)
                    self.app.logger.warning(msg)
                    continue

                print(query)

                for src in srcs:
                    if not dry_run:
                        self.app.downloads.add(src)

                    self.app.logger.info(str(src))

        else:
            # This code should never be reached but keeping it here we will
            # prevent future mistakes
            msg = "Incorrect usage"
            raise plugin.exc.PluginArgumentError(msg)

__arroyo_extensions__ = [
    ('download', DownloadCommand)
]
