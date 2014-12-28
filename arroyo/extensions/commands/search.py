from ldotcommons import utils

from arroyo.app import app, argument
from arroyo import selector
import arroyo.exc

from pprint import pprint


@app.register('command', 'search')
class QueryCommand:
    help = 'Query database'
    arguments = (
        argument(
            '-a', '--all',
            dest='all_states',
            action='store_true',
            help=('Include all results '
                  '(by default only sources with NONE state are displayed)')),
        argument(
            '-f', '--filter',
            dest='filters',
            required=False,
            type=str,
            action=utils.DictAction,
            help='Filters to apply in key_mod=value form'),
        argument(
            'keywords',
            nargs='*',
            help='Keywords.')
    )

    def run(self):
        filters = app.arguments.filters
        keywords = app.arguments.keywords

        if all([filters, keywords]):
            raise arroyo.exc.ArgumentError('Filters and keywords are mutually '
                                           'exclusive')

        queries = {}

        if keywords:
            queries = {
                ' '.join(keywords): selector.Query(
                    name_like='*' + '*'.join(keywords) + '*'
                )
            }

        elif filters:
            queries = {
                'command line': selector.Query(**filters)
            }

        else:
            queries = app.selector.get_queries()

        if not queries:
            raise arroyo.exc.ArgumentError(
                'One filter or one keyword or one [query.label] is required')

        # FIXME: Missing sync
        # sync()

        for (label, query) in queries.items():
            res = list(app.selector.select(query))

            msg = "- Search '{label}: {n_results} result(s)'"
            print(msg.format(label=label, n_results=len(res)))
            for src in res:
                print(src.pretty_repr)
