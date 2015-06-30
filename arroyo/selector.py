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

    #
    # This doesn't really fit here but it's better than anywhere else…
    #
    @property
    def filter_map(self):
        if self._filter_map is None:
            self._filter_map = {}

            for cls in self.app.get_implementations('filter').values():
                if cls.APPLIES_TO not in self.filter_map:
                    self._filter_map[cls.APPLIES_TO] = {}

                for key in cls.HANDLES:
                    if key in self._filter_map[cls.APPLIES_TO]:
                        msg = "{key} is currently mapped to {active}, ignoring {current}"
                        msg = msg.format(
                            key=key,
                            active=repr(self._filter_map[cls.APPLIES_TO][key]),
                            current=repr(cls))
                        self._logger.warning(msg)
                        continue

                    self._filter_map[cls.APPLIES_TO][key] = cls

        return self._filter_map
