from arroyo import exts


class Selector:
    def __init__(self, app):
        self.app = app
        self._auto_import = self.app.settings.get('auto-import')
        self._filter_map = None

    def get_queries_specs(self):
        return [exts.QuerySpec(x, **params) for (x, params) in
                self.app.settings.get_tree('query', {}).items()]

    def get_queries(self):
        return list(map(self.get_query_for_spec, self.get_queries_specs()))

    def get_query_for_spec(self, spec):
        return self.app.get_extension('query', spec.get('as'), spec=spec)

    def matches(self, everything, **params):
        spec = exts.QuerySpec(None, **params)
        query = self.get_query_for_spec(spec)
        return query.matches(everything)

    def select(self, **params):
        spec = exts.QuerySpec(None, **params)
        query = self.get_query_for_spec(spec)
        return query.select()

    def _build_filter_map(self):
        table = {}

        for filtercls in self.app.get_implementations('filter').values():
            for k in ((filtercls.APPLIES_TO, k) for k in filtercls.HANDLES):
                if k in table:
                    msg = ("{key} is currently mapped to {active}, "
                           "ignoring {current}")
                    msg = msg.format(
                        key=k,
                        active=repr(table[k]),
                        current=repr(filtercls))
                    self._logger.warning(msg)
                    continue

                table[k] = filtercls

        return table

    @property
    def filter_map(self):
        if not self._filter_map:
            self._filter_map = self._build_filter_map()

        return self._filter_map

    def get_filters(self, model, d={}):
        def instantiate_filter(k):
            return self.filter_map[(model, k)](self.app, k, d[k])

        registered = set(self.filter_map)
        required = set((model, x) for x in d)

        found = required.intersection(registered)
        # missing = required.difference(registered)

        return {(model, key): instantiate_filter(key)
                for (model, key) in found}
