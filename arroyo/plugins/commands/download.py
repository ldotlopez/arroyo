# -*- coding: utf-8 -*-

from arroyo import pluginlib
models = pluginlib.models
import re
import tabulate

from appkit import (
    logging,
    utils
)
import humanfriendly

import pprint
import itertools

SOURCE_FMT = "'{name}'"
LIST_FMT = ("[{state_symbol}] {id:5} '{name}' " +
            "(lang: {language}, size: {size}, ratio: {seeds}/{leechers})")


def format_source(src, fmt=SOURCE_FMT):
    d = {}

    if src.size:
        d['size'] = humanfriendly.format_size(src.size)

    return src.format(fmt, extra_data=d)


class SourceNotFoundError(Exception):
    pass


class FooCommand(pluginlib.Command):
    __extension_name__ = 'download'

    HELP = 'Download stuff'
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
            '--disable-scan',
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

    def source_from_id(self, id_):
        src = self.app.db.get(models.Source, id=id_)
        if not src:
            raise SourceNotFoundError(id_)

        return src

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
            if args.keywords:
                # Check for missuse of keywords
                if any([re.search(r'^([a-z]+)=(.+)$', x)
                        for x in args.keywords]):
                    msg = ("Found a filter=value argument without -f/--filter "
                           "flag")
                    self.app.logger.warning(msg)

                # Check for dangling filters
                if '-f' in args.keywords or '--filter' in args.keywords:
                    msg = "-f/--filter must be used *before* keywords"
                    self.app.logger.warning(msg)

                # Transform keywords into a usable query
                query = self.app.selector.get_query_from_string(
                    ' '.join([x.strip() for x in args.keywords]),
                    type_hint=args.filters.pop('kind', None))

                # ...and update it with supplied filters
                for (key, value) in args.filters.items():
                    query.params[key] = value

            elif args.filters:
                # Build the query from filters
                query = self.app.selector.get_query_from_params(
                    params=args.filters, display_name='command-line')

            queries = [query]

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
            for id_ in args.add:
                try:
                    self.app.downloads.add(self.source_from_id(id_))
                except SourceNotFoundError:
                    msg = "Source with ID={id} not found"
                    msg = msg.format(id=id_)
                    self.app.logger.error(msg)

        if args.remove:
            for id_ in args.remove:
                try:
                    self.app.downloads.remove(self.source_from_id(id_))
                except SourceNotFoundError:
                    msg = "Source with ID={id} not found"
                    msg = msg.format(id=id_)
                    self.app.logger.error(msg)

        if args.list:
            self.app.downloads.sync()
            for src in sorted(self.app.downloads.list(), key=lambda x: x.name):
                print(format_source(src, LIST_FMT))

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

            if not args.dry_run:
                for (entity, sources, selected) in selections:
                    msg = "Download added: #{id} {name}"
                    msg = msg.format(id=selected.id, name=selected.name)
                    self.app.downloads.add(selected)


def tabulate_groups(groups, *args, headers=None, **kwargs):
    if headers is None:
        headers = []

    data_rows = [x[1] for x in groups]

    table_str = tabulate.tabulate(data_rows)
    formated_rows = table_str.split("\n")

    pre = formated_rows[0]
    post = formated_rows[-1]
    formated_rows = formated_rows[1:-1]

    idx = 0
    for (entity, group) in itertools.groupby(groups, lambda x: x[0]):
        data = list([x[1] for x in group])

        yield (entity, formated_rows[idx:idx+len(data)])
        idx = idx + len(data)


def explain(selections):
    # Generate data for tabulate
    rows = []
    for (entity, sources, selected) in selections:
        for src in sources:
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
                humanfriendly.format_size(src.size)
                    if src.size else '',
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


__arroyo_extensions__ = [
    FooCommand
]
