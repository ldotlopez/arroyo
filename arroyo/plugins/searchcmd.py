# -*- coding: utf-8 -*-

from arroyo import plugin


import itertools
import re
import sys


from ldotcommons import utils


def fmt_src(src):
    return "{id:5d} [{icon}] {source}".format(
        icon=src.state_symbol,
        id=src.id,
        source=src)


def fmt_grp(prefix, iterable):
    return "\n".join([
        "{} {}".format(prefix, x) for x in iterable
        ])


class SearchCommand(plugin.Command):
    help = 'Search sources'

    arguments = (
        plugin.argument(
            '-a', '--all',
            dest='all_states',
            action='store_true',
            help=('include all results '
                  '(by default only sources with NONE state are displayed)')),

        plugin.argument(
            '-f', '--filter',
            dest='filters',
            required=False,
            default={},
            type=str,
            action=utils.DictAction,
            help='filters to apply in key_mod=value form'),

        plugin.argument(
            'keywords',
            nargs='*',
            help='keywords')
    )

    def run(self, args):
        all_states = args.all_states
        filters = args.filters
        keywords = args.keywords

        spec = {}

        if filters:
            spec.update(filters.items())

        if keywords:
            spec.update({'name-glob': '*' + '*'.join(keywords) + '*'})

        if spec:
            if 'query' in self.app.settings:
                self.app.settings.delete('query')

            self.app.settings.set('query.command-line', spec)

        specs = self.app.selector.get_queries_specs()
        if not specs:
            msg = 'One filter or one keyword or one [query.label] is required'
            raise plugin.exc.PluginArgumentError(msg)

        src_fmt = ("[{state_symbol}] {id} ({seeds}/{leechers}, {language}) "
                   "{name}")

        for spec in specs:
            # Get matches
            matches = self.app.selector.matches(spec,
                                                everything=all_states)

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
            print(msg.format(label=spec.name, n_results=len(matches)))

            for (entity, group) in groups:
                print('+ {}'.format(entity or 'Ungroupped'))
                print(fmt_grp('|-', (x.__str__(fmt=src_fmt) for x in group)))


__arroyo_extensions__ = [
    ('search', SearchCommand)
]
