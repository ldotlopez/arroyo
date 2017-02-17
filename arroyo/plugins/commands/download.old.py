# -*- coding: utf-8 -*-

from arroyo import pluginlib
models = pluginlib.models


from appkit import (
    logging,
    utils
)
import humanfriendly


class DownloadCommand(pluginlib.Command):
    __extension_name__ = 'download'

    HELP = 'Manage downloads'
    ARGUMENTS = (
        pluginlib.cliargument(
            '--import',
            dest='scan',
            action='store_true',
            default=None,
            help=('Import data from enabled providers before downloading '
                  'anything')),

        pluginlib.cliargument(
            '--no-import',
            dest='scan',
            action='store_false',
            default=None,
            help=('Disable automatic import process')),

        pluginlib.cliargument(
            '-l', '--list',
            dest='show',
            action='store_true',
            help='Show current downloads'),

        pluginlib.cliargument(
            '-a', '--add',
            dest='add',
            help='Download a source from its identifier'),

        pluginlib.cliargument(
            '-r', '--remove',
            dest='remove',
            help='Cancel a source downloading from its identifier'),

        pluginlib.cliargument(
            '-f', '--filter',
            dest='query',
            type=str,
            action=utils.DictAction,
            help=('Select and download sources using filters. See search '
                  'command for more help')),

        pluginlib.cliargument(
            '--from-config',
            dest='from_config',
            action='store_true',
            help=("Download sources from queries defined in the configuration "
                  "file")),

        pluginlib.cliargument(
            '-n', '--dry-run',
            dest='dry_run',
            action='store_true',
            help=("Dry run mode. Don't download anything, just show will be "
                  "downloaded"))
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

    def execute(self, args):
        def conditional_logger(level, msg):
            if not dry_run:
                self.app.logger.log(level.value, msg)
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
            raise pluginlib.exc.ArgumentsError(msg)

        elif test > 1:
            msg = "Only one action at time is supported"
            raise pluginlib.exc.ArgumentsError(msg)

        if show:
            for src in sorted(self.app.downloads.list(), key=lambda x: x.name):
                print(self.format_source(src, self.LIST_FMT))

            return

        elif source_id_add:
            src = self.app.db.get(models.Source, id=source_id)
            if src:
                msg = "Download added: " + self.format_source(
                    src, self.SOURCE_FMT)

                if not dry_run:
                    self.app.downloads.add(src)
                conditional_logger(logging.Level.INFO, msg)

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
                conditional_logger(logging.Level.INFO, msg)

            else:
                msg = "Source with id {id} not found"
                msg = msg.format(id=source_id)
                self.app.logger.error(msg)

            return

        if query:
            queries = [self.app.selector.get_query_from_params(
                params=query, display_name='command-line'
            )]

        elif from_config:
            queries = self.app.selector.get_configured_queries()

        if not queries:
            msg = "No queries specified"
            raise pluginlib.exc.ArgumentsError(msg)

        for query in queries:
            matches = self.app.selector.matches(query, auto_import=args.scan)

            srcs = list(self.app.selector.select(matches))
            if not srcs:
                msg = "No results for {name}"
                msg = msg.format(name=str(query))
                self.app.logger.error(msg)
                continue

            for src in srcs:
                msg = "Download added: " + self.format_source(
                    src, self.SOURCE_FMT)

                if not dry_run:
                    self.app.downloads.add(src)
                conditional_logger(logging.Level.INFO, msg)

__arroyo_extensions__ = [
    DownloadCommand
]
