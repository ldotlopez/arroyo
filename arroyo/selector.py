from ldotcommons import (sqlalchemy as ldotsa, utils)


class QuerySpec(utils.InmutableDict):
    def __init__(self, **kwargs):

        # Should all this normalization should be in BaseQuery?

        def _normalize_key(key):
            for x in [' ', '_']:
                key = key.replace(x, '-')
            return key

        tmp = {}
        for (k, v) in kwargs.items():
            k = _normalize_key(k)
            if k.endswith('-like'):
                v = ldotsa.glob_to_like(v, wide=True)
            tmp[k] = v

        kwargs = tmp

        if 'as' not in kwargs:
            kwargs['as'] = 'source'

        if 'language' in kwargs:
            kwargs['language'] = kwargs['language'].lower()

        if 'type' in kwargs:
            kwargs['type'] = kwargs['type'].lower()

        super().__init__(**kwargs)


class Selector:
    def __init__(self, app):
        self.app = app
        self._auto_import = self.app.settings.get('auto-import')

    def get_queries_specs(self):
        return {name: QuerySpec(**params) for (name, params) in
                self.app.settings.get_tree('query', {}).items()}

    def get_queries(self):
        return {name: self.get_query_for_spec(spec)
                for (name, spec) in self.get_queries_specs().items()}

    def get_query_for_spec(self, spec):
        return self.app.get_extension('query', spec.get('as'), spec=spec)

    # def get_selector(self, query):
    #     if not isinstance(query, QuerySpec):
    #         raise ValueError('query is not a QuerySpec object')

    #     selector_type = query.get('selector')
    #     query = query.exclude('selector')

    #     return self.app.get_extension(
    #         'selector', selector_type,
    #         query=query)

    def select_spec(self, spec, everything=False):
        if not isinstance(spec, QuerySpec):
            raise ValueError('query must be a Query instance')

        if self._auto_import:
            self.app.importer.import_query_spec(spec)

        self.app.downloads.sync()

        selector = self.get_selector(query)
        for src in selector.select(everything):
            yield src
