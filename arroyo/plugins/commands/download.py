# -*- coding: utf-8 -*-

from arroyo import pluginlib
models = pluginlib.models


import itertools
import re


from appkit import utils
import humanfriendly
import tabulate


class DownloadCommand(pluginlib.Command):
    __extension_name__ = 'download'

    HELP = 'Download (and search)'
    ARGUMENTS = (
        # Downloads management
        pluginlib.cliargument(
            '-a', '--add-id',
            dest='add',
            default=[],
            type=int,
            action='append',
            help='Download from a source ID'),

        pluginlib.cliargument(
            '-r', '--remove-id',
            dest='remove',
            default=[],
            type=int,
            action='append',
            help='Cancel a download from its source ID'),

        pluginlib.cliargument(
            '-l', '--list',
            dest='list',
            action='store_true',
            help='Show current downloads'),

        # Selecting
        pluginlib.cliargument(
            '--from-config',
            dest='from_config',
            action='store_true',
            help=("Download sources from queries defined in the configuration "
                  "file")),

        pluginlib.cliargument(
            '-f', '--filter',
            dest='filters',
            type=str,
            default={},
            action=utils.DictAction,
            help=('Select and download sources using filters. See search '
                  'command for more help')),

        # Behaviour control
        pluginlib.cliargument(
            '--force-scan',
            dest='scan',
            action='store_true',
            default=None,
            help=('Scan sources from enabled providers before downloading '
                  'anything')),

        pluginlib.cliargument(
            '--no-scan',
            dest='scan',
            action='store_false',
            default=None,
            help=('Disable automatic scan process')),

        pluginlib.cliargument(
            '--all',
            dest='everything',
            action='store_true',
            help=("Include all results. (including already downloader "
                  "sources, by default only sources with NONE state "
                  "are displayed).")),

        pluginlib.cliargument(
            '-n', '--dry-run',
            dest='dry_run',
            action='store_true',
            help=("Dry run mode. Don't download anything, just show what "
                  "will be downloaded.")),

        pluginlib.cliargument(
            '--explain',
            dest='explain',
            action='store_true',
            help=("Explain. Its encourage to use this option with --dry-run")),

        pluginlib.cliargument(
            'keywords',
            nargs='*',
            help='keywords')
    )

    def build_queries_from_args(self, filters, keywords):
        if keywords:
            # Check for missuse of keywords
            if any([re.search(r'^([a-z]+)=(.+)$', x)
                    for x in keywords]):
                msg = ("Found a filter=value argument without -f/--filter "
                       "flag")
                self.app.logger.warning(msg)

            # Check for dangling filters
            if '-f' in keywords or '--filter' in keywords:
                msg = "-f/--filter must be used *before* keywords"
                self.app.logger.warning(msg)

            # Transform keywords into a usable query
            query = self.app.selector.get_query_from_string(
                ' '.join([x.strip() for x in keywords]),
                type_hint=filters.pop('kind', None))

            # ...and update it with supplied filters
            for (key, value) in filters.items():
                query.params[key] = value

        elif filters:
            # Build the query from filters
            query = self.app.selector.get_query_from_params(
                params=filters, display_name='command-line')

        return [query]

    def add_downloads(self, downloads, dry_run=False):
        for src in downloads:
            if isinstance(src, int):
                src = self.app.db.get(models.Source, id=src)

                if not src:
                    msg = "Source with ID={id} not found"
                    msg = msg.format(id=src)
                    self.app.logger.error(msg)

            if not isinstance(src, models.Source):
                raise TypeError(src)

            msg = "Download added: «{source}»"
            msg = msg.format(source=src.name)

            if dry_run:
                print(msg)
            else:
                self.app.downloads.add(src)
                self.app.logger.info(msg)

    def remove_downloads(self, downloads, dry_run=False):
        for src in downloads:
            if isinstance(src, int):
                src = self.app.db.get(models.Source, id=src)

                if not src:
                    msg = "Source with ID={id} not found"
                    msg = msg.format(id=src)
                    self.app.logger.error(msg)

            if not isinstance(src, models.Source):
                raise TypeError(src)

            msg = "Download removed: «{source}»"
            msg = msg.format(source=src.name)

            if dry_run:
                print(msg)
            else:
                self.app.downloads.remove(src)
                self.app.logger.info(msg)

    def execute(self, args):
        # Direct download management:
        # --add / --remove / --list
        # Conflicts with:
        # --filter / keywords

        #
        # Build queries from configuration, filter arguments or keywords
        #
        queries = []

        if args.filters or args.keywords:
            queries = self.build_queries_from_args(args.filters, args.keywords)

        if args.from_config:
            queries = self.app.selector.get_configured_queries()
            if not queries:
                msg = "No configured queries"
                self.app.logger.error(msg)
                raise pluginlib.ConfigurationError(msg)

        #
        # Handle user will
        #

        if args.add:
            self.add_downloads(args.add, dry_run=args.dry_run)

        if args.remove:
            self.remove_downloads(args.remove, dry_run=args.dry_run)

        if args.list:
            self.app.downloads.sync()

            downloads = self.app.downloads.list()
            if not downloads:
                msg = "No downloads"
                print(msg)

            else:
                rows = [tabulated_data_from_source(src)
                        for src in sorted(downloads, key=lambda x: x.name)]

                formated_table = filtered_tabulate(
                    rows,
                    keys=['state_symbol', 'id', 'name', 'size', 'language',
                          'ratio'],
                    headers=['State', 'ID', 'Name', 'Size', 'Language',
                             'Seed ratio'])
                print(formated_table)

        for query in queries:
            srcs = self.app.selector.matches(query,
                                             auto_import=args.scan,
                                             everything=args.everything)

            # Build selections
            selections = []
            for (entity, sources) in self.app.selector.group(srcs):
                if len(sources) > 1:
                    selected = self.app.selector.select(sources)
                else:
                    selected = sources[0]

                selections.append((entity, sources, selected))

            if args.explain:
                explain(selections)

            self.add_downloads(
                [selected for (dummy, dummy, selected) in selections],
                dry_run=args.dry_run)


def explain(selections):
    # Generate data for tabulate
    rows = []

    for (entity, sources, selected) in selections:
        for src in sources:
            # srcdata = tabulated_data_from_source(src)
            # srcdata['selected'] = '→' if src == selected else ''
            # rows.append(srcdata)

            rows.append((entity, (
                # Source ID
                src.id,
                # This this source the selected one?
                '→' if src == selected else '',
                # Source state
                '[{}]'.format(src.state_symbol),
                # Source name
                src.name,
                # Souce size
                humanfriendly.format_size(src.size) if src.size else '',
                # Source language if applicable
                src.language or '',
                # s/l ratio
                '{}/{}'.format(src.seeds or '-', src.leechers or '-'),
            )))

    # headers = ['ID', 'selected', 'state', 'name', 'size', 'language',
    #            'ratio']
    groupped_rows = tabulate_groups(rows)
    for (entity, rows) in groupped_rows:
        header = "[{type}] {entity}"
        header = header.format(
            type=entity.__class__.__name__.capitalize(),
            entity=entity)

        print("{header}\n{rows}\n".format(header=header,
                                          rows="\n".join(rows)))


def tabulate_groups(groups, *args, headers=None, **kwargs):
    if headers is None:
        headers = []

    data_rows = [x[1] for x in groups]

    table_str = tabulate.tabulate(data_rows)
    formated_rows = table_str.split("\n")

    # dummy = formated_rows[0]
    # dummy = formated_rows[-1]
    formated_rows = formated_rows[1:-1]

    idx = 0
    for (entity, group) in itertools.groupby(groups, lambda x: x[0]):
        data = list([x[1] for x in group])

        yield (entity, formated_rows[idx:idx+len(data)])
        idx = idx + len(data)


def tabulated_data_from_source(source):
    ret = source.as_dict()

    ret.update({
        'state_symbol': '[{}]'.format(source.state_symbol),
        'size': humanfriendly.format_size(source.size)if source.size else '',
        'language': source.language or ' ',
        'ratio': '{}/{}'.format(source.seeds or '-', source.leechers or '-'),
    })

    return ret


def filtered_tabulate(rows, *args, keys=None, **kwargs):
    data = []
    for row in rows:
        data.append([row[k] for k in keys])

    return tabulate.tabulate(data, *args, **kwargs)

__arroyo_extensions__ = [
    DownloadCommand
]
