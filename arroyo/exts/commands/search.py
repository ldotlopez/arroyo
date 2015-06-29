import itertools
import re

from ldotcommons import utils


from arroyo import (
    exc,
    exts,
    selector
)


def fmt_src(src):
    return "{id:5d} [{icon}] {source}".format(
        icon=src.state_symbol,
        id=src.id,
        source=src)


def fmt_grp(prefix, iterable):
    return "\n".join([
        "{} {}".format(prefix, x) for x in iterable
        ])


class QueryCommand(exts.Command):
    help = 'Search sources'

    arguments = (
        exts.argument(
            '-a', '--all',
            dest='all_states',
            action='store_true',
            help=('include all results '
                  '(by default only sources with NONE state are displayed)')),

        exts.argument(
            '--auto-import',
            dest='auto_import',
            action='store_true',
            help=('Enable dynamic search')),

        exts.argument(
            '-f', '--filter',
            dest='filters',
            required=False,
            default={},
            type=str,
            action=utils.DictAction,
            help='filters to apply in key_mod=value form'),

        exts.argument(
            'keywords',
            nargs='*',
            help='keywords')
    )

    def run(self, args):
        all_states = args.all_states
        filters = args.filters
        keywords = args.keywords

        self.app.settings.set('auto-import', args.auto_import)

        if all([filters, keywords]):
            raise exc.ArgumentError('Filters and keywords are mutually '
                                    'exclusive')

        if keywords:
            self.app.settings.delete('query')

            query_name = ' '.join(keywords)
            query_name = re.sub(r'[^\sa-zA-Z0-9_\-\.]', '', query_name).strip()
            self.app.settings.set(
                'query.' + query_name + '.name-like',
                '*' + '*'.join(keywords) + '*')

        elif filters:
            self.app.settings.delete('query')

            for (k, v) in filters.items():
                self.app.settings.set('query.command-line.' + k, v)

        queries = self.app.selector.get_queries()
        if not queries:
            msg = 'One filter or one keyword or one [query.label] is required'
            raise exc.ArgumentError(msg)

        for query in self.app.selector.get_queries():
            matches = query.matches(everything=all_states)

            groups = itertools.groupby(matches, lambda src: src.superitem)

            msg = "== Search '{label}: {n_results} result(s)'"
            print(msg.format(label=query.name, n_results=len(matches)))

            for (superitem, grouper) in groups:
                print('+ {}'.format(superitem or 'Ungroupped'))
                print(fmt_grp('|-', (fmt_src(x) for x in grouper)))


__arroyo_extensions__ = [
    ('command', 'search', QueryCommand)
]
