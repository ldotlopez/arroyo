# -*- coding: utf-8 -*-

from arroyo import models, plugin


import itertools
import sys


import humanfriendly
from ldotcommons import utils


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

    SOURCE_FMT = "{state_symbol} {id:5d} " + models.Source.Formats.DETAIL

    @classmethod
    def format_source(cls, src):
        d = {}

        if src.size:
            d['size'] = humanfriendly.format_size(src.size)

        return src.format(
            cls.SOURCE_FMT,
            extra_data=d)

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

        for spec in specs:
            # Get matches
            matches = self.app.selector.matches(
                spec,
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
                print('{}'.format(entity or 'Ungroupped'))
                lines = [self.format_source(x) for x in group]
                print("\n".join(lines) + "\n")


__arroyo_extensions__ = [
    ('search', SearchCommand)
]
