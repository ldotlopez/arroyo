# -*- coding: utf-8 -*-

from arroyo import pluginlib
models = pluginlib.models


import itertools
import sys


import humanfriendly
from appkit import utils


def entity_key_func(x):
    if x.entity is None:
        return ('', -sys.maxsize)
    else:
        return (x.entity.__class__.__name__, x.id)


class SearchCommand(pluginlib.Command):
    __extension_name__ = 'search'

    HELP = 'Search sources'
    ARGUMENTS = (
        pluginlib.cliargument(
            '--import',
            dest='scan',
            action='store_true',
            default=None,
            help=('Force auto import')),

        pluginlib.cliargument(
            '--no-import',
            dest='scan',
            action='store_false',
            default=None,
            help=('Disable auto import')),

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
        matches = self.app.selector.matches(query,
                                            everything=all_states,
                                            auto_import=args.scan)

        # Sort matches by entity ID
        matches = sorted(
            matches,
            key=lambda x: entity_key_func(x))

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
            if not entity:
                header = "Ungroupped"
            else:
                header = "[{type}] {entity}"
                header = header.format(
                    type=entity.__class__.__name__.capitalize(),
                    entity=entity)

            lines = "\n".join([self.format_source(x) for x in group])

            print(header + "\n" + lines + "\n")


__arroyo_extensions__ = [
    SearchCommand
]
