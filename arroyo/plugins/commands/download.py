# -*- coding: utf-8 -*-

# Copyright (C) 2015 Luis López <luis@cuarentaydos.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301,
# USA.


from arroyo import (
    downloads,
    selector,
    pluginlib
)


import itertools
import functools
import re
import sys


import humanfriendly
import tabulate
from appkit import (
    loggertools,
    utils
)


models = pluginlib.models


class CommonMixin:
    ARGUMENTS = (
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
            '--explain',
            dest='explain',
            action='store_true',
            help=("Explain. Its encourage to use this option with --dry-run")),

        pluginlib.cliargument(
            'keywords',
            nargs='*',
            help='keywords')
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = loggertools.getLogger(self.__extension_name__)

    def execute(self, app, arguments):
        # FIXME: Deprecated code
        if arguments.everything:
            msg = "--all flag is deprecated. Use -f state=all"
            self.logger.warning(msg)
            arguments.filters['state'] = 'all'

        queries = []

        #
        # Build queries from configuration, filter arguments or keywords
        #
        if arguments.keywords:
            # Check for missuse of keywords
            if any([re.search(r'^([a-z]+)=(.+)$', x)
                    for x in arguments.keywords]):
                msg = ("Found a filter=value argument without -f/--filter "
                       "flag")
                self.logger.warning(msg)

            # FIXME: Do this with arguments
            # Join keywords
            arguments.keywords = ' '.join([x.strip()
                                           for x in arguments.keywords])

        if arguments.keywords or arguments.filters:
            queries = [
                ('command-line',
                 app.selector.query_from_args(
                     keyword=arguments.keywords,
                     params=arguments.filters))
            ]

        if arguments.from_config:
            queries = app.selector.queries_from_config()
            if not queries:
                msg = "No configured queries"
                self.logger.error(msg)
                raise pluginlib.exc.ConfigurationError(msg)

        delattr(arguments, 'keywords')
        delattr(arguments, 'filters')
        delattr(arguments, 'from_config')
        setattr(arguments, 'queries', queries)

    def search(self, query, auto_import=None):
        srcs = self.app.selector.matches(
            query,
            auto_import=auto_import)

        if not srcs:
            msg = "No matches found"
            print(msg, file=sys.stderr)
            return []

        # Build selections
        results = []
        for (entity, sources) in self.app.selector.group(srcs):
            selected = self.app.selector.select(sources)
            results.append((entity, sources, selected))

        return results


class SearchCommand(CommonMixin, pluginlib.Command):
    __extension_name__ = 'search'
    ARGUMENTS = CommonMixin.ARGUMENTS
    HELP = 'Search stuff'

    def execute(self, app, arguments):
        super().execute(app, arguments)

        if not arguments.queries:
            msg = "Nothing to search"
            self.logger.error(msg)
            return

        for (name, query) in arguments.queries:
            try:
                results = self.search(query, auto_import=arguments.scan)
            except (selector.FilterNotFoundError,
                    selector.FilterCollissionError) as e:
                print(e, file=sys.stderr)
                continue

            print(explain(results))


class DownloadCommand(CommonMixin, pluginlib.Command):
    __extension_name__ = 'download'

    HELP = 'Control downloads'
    ARGUMENTS = CommonMixin.ARGUMENTS + (
        pluginlib.cliargument(
            '-a', '--add-id',
            dest='add',
            default=[],
            type=int,
            action='append',
            help='Download from a source ID'),

        pluginlib.cliargument(
            '-c', '--cancel-id',
            dest='cancel',
            default=[],
            type=int,
            action='append',
            help='Cancel a download from its source ID'),

        pluginlib.cliargument(
            '-x', '--archive-id',
            dest='archive',
            default=[],
            type=int,
            action='append',
            help='Cancel a download from its source ID'),

        pluginlib.cliargument(
            '-l', '--list',
            dest='list',
            action='store_true',
            help='Show current downloads'),

        pluginlib.cliargument(
            '-n', '--dry-run',
            dest='dry_run',
            action='store_true',
            help=("Dry run mode. Don't download anything, just show what "
                  "will be downloaded.")),

    )

    def ensure_sources(self, objs):
        ret = []
        for obj in objs:
            if isinstance(obj, models.Source):
                ret.append(obj)

            else:
                source = self.app.db.get(models.Source, id=obj)
                if not source:
                    msg = "No source found for '{id}'"
                    msg = msg.format(id=obj)
                    self.logger.error(msg)
                    continue

                ret.append(source)

        return ret

    def _fn_download(self, fn, verb, ids, dry_run=False):
        def _fake_op(args):
            return [None] * len(args)

        if not ids:
            return []

        sources = self.ensure_sources(ids)
        if dry_run:
            fn_ = _fake_op
        else:
            fn_ = fn

        ok_msg = "Download {verb}: «{source}»"

        for (src, ret) in zip(sources, fn_(sources)):
            if isinstance(ret, downloads.DuplicatedDownloadError):
                msg = "Duplicated download: {src}"
                msg = msg.format(src=src)
                self.logger.error(msg)
                continue

            elif isinstance(ret, downloads.DownloadNotFoundError):
                msg = "Missing download: {src}"
                msg = msg.format(src=src)
                self.logger.error(msg)
                continue

            elif isinstance(ret, downloads.ResolveLazySourceError):
                msg = "Unable to resolve «{src}» (uri: «{uri}»)"
                msg = msg.format(src=src, uri=src.uri)
                self.logger.error(msg)
                continue

            elif isinstance(ret, Exception):
                raise ret

            msg = ok_msg.format(source=src, verb=verb)
            print(msg)

    def add_downloads(self, ids, dry_run=False):
        return self._fn_download(
            self.app.downloads.add_all, 'added', ids, dry_run=dry_run)

    def archive_downloads(self, ids, dry_run=False):
        return self._fn_download(
            self.app.downloads.archive_all, 'removed', ids, dry_run=dry_run)

    def cancel_downloads(self, ids, dry_run=False):
        return self._fn_download(
            self.app.downloads.cancel_all, 'removed', ids, dry_run=dry_run)

    def list_downloads(self):
        downloads = self.app.downloads.list()
        if not downloads:
            msg = "No downloads"
            print(msg)

        else:
            rows = [tabulated_data_from_source(src)
                    for src in sorted(downloads, key=lambda x: x.name)]

            print(tabulate_(
                rows,
                keys=['state_symbol', 'id', 'name', 'size', 'language',
                      'ratio'],
                headers=['State', 'ID', 'Name', 'Size', 'Language',
                         'Seed ratio']))

    def execute(self, app, arguments):
        super().execute(app, arguments)

        if arguments.add:
            self.add_downloads(arguments.add,
                               dry_run=arguments.dry_run)

        if arguments.archive:
            self.archive_downloads(arguments.archive,
                                   dry_run=arguments.dry_run)

        if arguments.cancel:
            self.cancel_downloads(arguments.cancel,
                                  dry_run=arguments.dry_run)

        if arguments.list:
            self.list_downloads()

        for (name, query) in arguments.queries:
            results = self.search(query, auto_import=arguments.scan)
            if arguments.explain:
                explain(results)

            self.add_downloads(
                [selected for (dummy, dummy, selected) in results],
                dry_run=arguments.dry_run)


def tabulated_data_from_source(source, selected=False):
    ret = source.asdict()

    if source.download:
        state_symbol = models.STATE_SYMBOLS[source.download.state]
    else:
        state_symbol = ' '

    ret.update({
        'state_symbol': '[{}]'.format(state_symbol),
        'size': humanfriendly.format_size(source.size)if source.size else '',
        'language': source.language or ' ',
        'ratio': '{}/{}'.format(source.seeds or '-', source.leechers or '-'),
        'selected': '*' if selected else ''
    })

    return ret


def explain(results):
    """Wrapper around display_groupped
    """
    groups = []
    for (entity, sources, selected_source) in results:
        group_data = []

        for source in sources:
            source_data = tabulated_data_from_source(
                source,
                selected=(source == selected_source))
            group_data.append(source_data)

        groups.append((entity, group_data))

    keys = ['id', 'selected', 'name', 'size', 'language',  'ratio']
    headers = ['ID', '', 'Name', 'Size', 'Language', 'Seed ratio']

    display_groupped(groups, keys=keys, headers=headers)


def display_groupped(groups, keys, headers):
    # Unroll groups
    data = []
    for (master, row_group) in groups:
        for row in row_group:
            data.append((master, row))

    formatted = tabulate_(
        (x[1] for x in data),
        keys=keys,
        headers=headers)
    rows = formatted.split('\n')
    text_header, text_separator, text_rows = (rows[0], rows[1], rows[2:])

    masters_and_text_rows = zip(
        (x[0] for x in data),  # master of each group
        text_rows              # Rows relative to that master
    )

    it = sorted(
        masters_and_text_rows,
        key=functools.cmp_to_key(lambda a, b: cmp_entities(a[0], b[0]))
    )
    it = itertools.groupby(it, lambda x: x[0])

    for (master, group) in it:
        master_type = camel_case(master.__class__.__name__)
        master_text = camel_case(str(master))

        print("» [{type} - {master}]".format(
            type=master_type,
            master=master_text
        ))
        print("   "+text_header)
        print("   "+text_separator)
        for (dummy, text_row) in group:
            print("   "+text_row)
        print("   "+text_separator)
        print("")


def tabulate_(rows, *args, keys=None, **kwargs):
    """Wrapper function for tabulate.tabule

    Adds keys paramter.
    """
    if keys is None:
        keys = []

    return tabulate.tabulate(
        [[row[k] for k in keys] for row in rows],
        *args, **kwargs
    )


def camel_case(s):
    return ' '.join(x.capitalize() for x in s.split())


def cmp_entities(a, b):
    # Check different class
    if a.__class__ is not b.__class__:
        if a.__class__ is models.Source:
            return -1

        if b.__class__ is models.Source:
            return 1

        return a.__class__.__name__ < b.__class__.__name__

    return str(a) < str(b)


__arroyo_extensions__ = [
    DownloadCommand,
    SearchCommand
]
