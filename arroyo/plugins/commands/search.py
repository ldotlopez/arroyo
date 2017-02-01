# -*- coding: utf-8 -*-

from arroyo import pluginlib
models = pluginlib.models


import itertools
import sys


import humanfriendly
from appkit import utils


class SearchCommand(pluginlib.Command):
    __extension_name__ = 'search'

    HELP = 'Search sources'
    ARGUMENTS = (
        pluginlib.cliargument(
            '-a', '--all',
            dest='all_states',
            action='store_true',
            help=('include all results '
                  '(by default only sources with NONE state are displayed)')),

        pluginlib.cliargument(
            '-f', '--filter',
            dest='filters',
            required=False,
            default={},
            type=str,
            action=utils.DictAction,
            help='filters to apply in key_mod=value form'),

        pluginlib.cliargument(
            'keywords',
            nargs='*',
            help='keywords')
    )

    SOURCE_FMT = "{state_symbol} {id:5d} " + models.Source.Formats.DETAIL

    @classmethod
    def format_source(cls, src):
        d = {}

        if src.size:
            d['size'] = humanfriendly.format_size(src.size)

        return src.format(
            cls.SOURCE_FMT,
            extra_data=d)

    def execute(self, args):
        all_states = args.all_states
        filters = args.filters
        keywords = args.keywords

        params = {}

        if filters:
            params.update(filters.items())

        if keywords:
            params.update({'name-glob': '*' + '*'.join(keywords) + '*'})

        if not params:
            msg = "Al least one filter or keyword must be specified"
            raise pluginlib.exc.ArgumentsError(msg)

        query = self.app.selector.get_query_from_params(
            params=params, display_name='command-line'
        )

        # Get matches
        matches = self.app.selector.matches(query, everything=all_states)

        # Sort matches by entity ID
        matches = sorted(
            matches,
            key=lambda x: -sys.maxsize
            if x.entity is None else x.entity.id)

        # Group by entity
        groups = itertools.groupby(
            matches,
            lambda x: x.entity)

        # Unfold groups
        groups = ((grp, list(srcs)) for (grp, srcs) in groups)

        # Order by entity str
        groups = sorted(
            groups,
            key=lambda x: str(x[0]).lower() if x[0] else '')

        # Finally print
        msg = "== Search '{label}: {n_results} result(s)'"
        print(msg.format(label=str(query), n_results=len(matches)))

        for (entity, group) in groups:
            print('{}'.format(entity or 'Ungroupped'))
            lines = [self.format_source(x) for x in group]
            print("\n".join(lines) + "\n")


__arroyo_extensions__ = [
    SearchCommand
]
