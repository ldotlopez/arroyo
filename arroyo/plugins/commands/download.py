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


import itertools
import re
import sys


import humanfriendly
import tabulate
from appkit import (
    loggertools,
    utils
)
from arroyo import (
    selector,
    pluginlib
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
                raise pluginlib.ConfigurationError(msg)

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
        selections = []
        for (entity, sources) in self.app.selector.group(srcs):
            selected = self.app.selector.select(sources)
            selections.append((entity, sources, selected))

        return selections


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

            if arguments.explain:
                explain(results)
            else:
                for (dummy, dummy, selected) in results:
                    print(selected)


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
        def _fake_op(*args):
            return [None] * len(args)

        sources = self.ensure_sources(ids)
        if dry_run:
            fn_ = _fake_op
        else:
            fn_ = fn

        ok_msg = "Download {verb}: «{source}»"
        error_msg = "{source}: {e}"

        for (src, ret) in zip(sources, fn_(sources)):
            if isinstance(ret, Exception):
                msg = error_msg.format(source=src, e=ret)
                self.logger.error(msg)
                continue

            msg = ok_msg.format(source=src, verb=verb)
            print(msg)

    def add_downloads(self, ids, dry_run=False):
        return self._fn_download(self.app.downloads.add_all, 'added', ids,
                                 dry_run=dry_run)

    def remove_downloads(self, ids, dry_run=False):
        return self._fn_download(self.app.downloads.remove_all, 'removed', ids,
                                 dry_run=dry_run)

    def list_downloads(self):
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

    def execute(self, app, arguments):
        super().execute(app, arguments)

        if arguments.add:
            self.add_downloads(arguments.add,
                               dry_run=arguments.dry_run)

        if arguments.remove:
            self.remove_downloads(arguments.remove,
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
    ret = source.asdict()

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
    DownloadCommand,
    SearchCommand
]
