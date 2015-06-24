from ldotcommons import (sqlalchemy as ldotsa, utils)


class QuerySpec(utils.InmutableDict):
    def __init__(self, **kwargs):
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

        if 'selector' not in kwargs:
            kwargs['selector'] = 'source'

        if 'language' in kwargs:
            kwargs['language'] = kwargs['language'].lower()

        if 'type' in kwargs:
            kwargs['type'] = kwargs['type'].lower()

        super().__init__(**kwargs)


class Selector:
    def __init__(self, app):
        self.app = app
        self._auto_import = self.app.settings.get('auto-import')

    def get_queries(self):
        cfg_dict = utils.configparser_to_dict(self.app.config)
        queries = utils.MultiDepthDict(cfg_dict).subdict('query')
        return {k: QuerySpec(**v) for (k, v) in queries.items()}

    def get_selector(self, query):
        if not isinstance(query, QuerySpec):
            raise ValueError('query is not a QuerySpec object')

        selector_type = query.get('selector')
        query = query.exclude('selector')

        return self.app.get_extension(
            'selector', selector_type,
            query=query)

    def select(self, query, everything=False):
        if not isinstance(query, QuerySpec):
            raise ValueError('query must be a Query instance')

        if self._auto_import:
            self.app.importer.import_query_spec(query)

        selector = self.get_selector(query)
        for src in selector.select(everything):
            yield src
