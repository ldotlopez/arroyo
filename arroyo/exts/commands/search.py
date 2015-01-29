import itertools


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
    help = 'Query database'
    arguments = (
        exts.argument(
            '-a', '--all',
            dest='all_states',
            action='store_true',
            help=('Include all results '
                  '(by default only sources with NONE state are displayed)')),
        exts.argument(
            '-f', '--filter',
            dest='filters',
            required=False,
            type=str,
            action=utils.DictAction,
            help='Filters to apply in key_mod=value form'),
        exts.argument(
            'keywords',
            nargs='*',
            help='Keywords.')
    )

    def run(self):
        filters = self.app.arguments.filters
        keywords = self.app.arguments.keywords

        if all([filters, keywords]):
            raise exc.ArgumentError('Filters and keywords are mutually '
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
            queries = self.app.selector.get_queries()

        if not queries:
            raise exc.ArgumentError(
                'One filter or one keyword or one [query.label] is required')

        # FIXME: Missing sync
        # sync()
        for (label, query) in queries.items():
            res = list(self.app.selector.select(query, download=False))

            msg = "== Search '{label}: {n_results} result(s)'"
            print(msg.format(label=label, n_results=len(res)))
            grouping = itertools.groupby(res, lambda src: src.superitem)
            for (superitem, grouper) in grouping:
                print('+ {}'.format(superitem or 'Ungroupped'))
                print(fmt_grp('|-', (fmt_src(x) for x in grouper)))


__arroyo_extensions__ = [
    ('command', 'search', QueryCommand)
]
