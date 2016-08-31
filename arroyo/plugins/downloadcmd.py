# -*- coding: utf-8 -*-

from arroyo import plugin


import humanfriendly
from appkit import logging, utils


models = plugin.models


class DownloadCommand(plugin.Command):
    __extension_name__ = 'download-command'

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

    SOURCE_FMT = "'{name}'"
    LIST_FMT = ("[{state_symbol}] {id:5} '{name}' " +
                "(lang: {language}, size: {size}, ratio: {seeds}/{leechers})")

    @staticmethod
    def format_source(src, fmt):
        d = {}

        if src.size:
            d['size'] = humanfriendly.format_size(src.size)

        return src.format(fmt, extra_data=d)

    def conditional_logger(level, msg):
        if not dry_run:
            self.app.logger(level, msg)
        else:
            print(msg)

    def run(self, args):
        def conditional_logger(level, msg):
            if not dry_run:
                self.app.logger.log(level, msg)
            else:
                print(msg)

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

        test = sum([1 for x in (show, add, remove, query, from_config) if x])

        if test == 0:
            msg = "No action specified"
            raise plugin.exc.PluginArgumentError(msg)

        elif test > 1:
            msg = "Only one action at time is supported"
            raise plugin.exc.PluginArgumentError(msg)

        if show:
            for src in self.app.downloads.list():
                print(self.format_source(src, self.LIST_FMT))

            return

        elif source_id_add:
            src = self.app.db.get(models.Source, id=source_id)
            if src:
                msg = "Download added: " + self.format_source(
                    src, self.SOURCE_FMT)

                if not dry_run:
                    self.app.downloads.add(src)
                conditional_logger(logging.INFO, msg)

            else:
                msg = "Source with id {id} not found"
                msg = msg.format(id=source_id)
                self.app.logger.error(msg)

            return

        elif source_id_remove:
            src = self.app.db.get(models.Source, id=source_id)
            if src:
                msg = "Download removed: " + self.format_source(
                    src, self.SOURCE_FMT)
                if not dry_run:
                    self.app.downloads.remove(src)
                conditional_logger(logging.INFO, msg)

            else:
                msg = "Source with id {id} not found"
                msg = msg.format(id=source_id)
                self.app.logger.error(msg)

            return

        if query:
            specs = [plugin.QuerySpec('command-line', **query)]

        elif from_config:
            specs = self.app.selector.get_queries_specs()

        if not specs:
            msg = "No queries specified"
            raise plugin.exc.PluginArgumentError(msg)

        for spec in specs:
            matches = self.app.selector.matches(spec)
            srcs = list(self.app.selector.select(matches))
            if not srcs:
                msg = "No results for {name}"
                msg = msg.format(name=spec.name)
                self.app.logger.error(msg)
                continue

            for src in srcs:
                msg = "Download added: " + self.format_source(
                    src, self.SOURCE_FMT)

                if not dry_run:
                    self.app.downloads.add(src)
                conditional_logger(logging.INFO, msg)

__arroyo_extensions__ = [
    DownloadCommand
]
