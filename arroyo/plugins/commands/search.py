# -*- coding: utf-8 -*-

from arroyo import pluginlib
models = pluginlib.models


import itertools
import sys


import humanfriendly
from appkit import utils


class SearchCommand(pluginlib.Command):
    __extension_name__ = 'search'

    HELP = 'Search for sources'
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
        # Check for correct usage
        if not args.filters and not args.keywords:
            msg = "Al least one filter or keyword must be specified"
            raise pluginlib.exc.ArgumentsError(msg)

        # Create query from keywords
        if args.keywords:
            query = self.app.selector.get_query_from_string(
                ' '.join([x.strip() for x in args.keywords]),
                type_hint=args.filters.pop('kind', None))

            for (key, value) in args.filters:
                query.params[key] = value

        elif args.filters:
            query = self.app.selector.get_query_from_params(
                params=args.filters, display_name='command-line')

        else:
            raise SystemError('Should not reach.')

        # Get matches
        matches = self.app.selector.matches(query,
                                            everything=args.all_states,
                                            auto_import=args.scan)

        n_matches = len(matches)
        groupping = self.app.selector.group(matches)

        # Finally print
        msg = "== Search '{label}: {n_results} result(s)'"
        msg = msg.format(label=str(query), n_results=len(matches))
        print(msg)

        for (entity, group) in groupping:
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
