import itertools
import sys


from arroyo import exts


class Selector:
    def __init__(self, app):
        self.app = app

    def get_queries_specs(self):
        return [exts.QuerySpec(x, **params) for (x, params) in
                self.app.settings.get_tree('query', {}).items()]

    def get_queries(self):
        return list(map(self.get_query_for_spec, self.get_queries_specs()))

    def get_query_for_spec(self, spec):
        base = self.app.settings.get_tree(
            'selector.query-defaults', {})
        specific = self.app.settings.get_tree(
            'selector.query-{}-defaults'.format(spec.get('kind')), {})

        base.update(specific)
        base.update(spec)
        spec = exts.QuerySpec(spec.name, **base)

        return self.app.get_extension('query', spec.get('kind'), spec=spec)

    def _auto_import(self, query):
        if self.app.settings.get('auto-import'):
            self.app.importer.import_query_spec(query.spec)

    def matches(self, spec, everything=False):
        query = self.get_query_for_spec(spec)
        self._auto_import(query)
        ret = query.matches(everything)

        return sorted(
            ret,
            key=lambda x: -sys.maxsize
            if x.superitem is None else x.superitem.id)

    def sort(self, items):
        sorter = self.app.get_extension(
            'sorter',
            self.app.settings.get('selector.sorter', 'basic'))

        groups = itertools.groupby(items, lambda src: src.superitem)

        ret = []
        for (superitem, group) in groups:
            ret += list(sorter.sort(group))

        return ret

    def select(self, spec):
        sorter = self.app.get_extension(
            'sorter',
            self.app.settings.get('selector.sorter', 'basic'))

        query = self.matches(spec, everything=False)

        groups = itertools.groupby(query, lambda src: src.superitem)

        ret = []
        for (superitem, group) in groups:
            r = iter(sorter.sort(group))
            ret.append(next(r))

        return ret

    def get_filters(self, models, params):
        table = {}

        for filtercls in self.app.get_implementations('filter').values():
            if filtercls.APPLIES_TO not in models:
                continue

            for k in [k for k in filtercls.HANDLES if k in params]:
                if k not in table:
                    table[k] = filtercls
                else:
                    msg = ("{key} is currently mapped to {active}, "
                           "ignoring {current}")
                    msg = msg.format(
                        key=k,
                        active=repr(table[k]),
                        current=repr(filtercls))
                    self.app.logger.warning(msg)

        return {k: table[k](self.app, k, params[k]) for k in table}

    def apply_filters(self, qs, models, params):
        guessed_models = itertools.chain(qs._entities, qs._join_entities)
        guessed_models = [x.mapper.class_ for x in guessed_models]
        assert set(guessed_models) == set(models)

        filters = self.get_filters(guessed_models, params)

        missing = set(params).difference(set(filters))

        sql_aware = {True: [], False: []}
        for f in filters.values():
            test = f.__class__.alter_query != exts.Filter.alter_query
            sql_aware[test].append(f)

        for f in sql_aware.get(True, []):
            qs = f.alter_query(qs)

        items = (x for x in qs)
        for f in sql_aware.get(False, []):
            items = f.apply(items)

        return items, missing
