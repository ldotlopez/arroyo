from ldotcommons import (sqlalchemy as ldotsa, utils)


class QuerySpec(utils.InmutableDict):
    def __init__(self, name, **kwargs):

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
        self._name = name

    @property
    def name(self):
        return self._name


class Selector:
    def __init__(self, app):
        self.app = app
        self._auto_import = self.app.settings.get('auto-import')

    def get_queries_specs(self):
        return [QuerySpec(name, **params) for (name, params) in
                self.app.settings.get_tree('query', {}).items()]

    def get_queries(self):
        return list(map(self.get_query_for_spec, self.get_queries_specs()))

    def get_query_for_spec(self, spec):
        return self.app.get_extension('query', spec.get('as'), spec=spec)
