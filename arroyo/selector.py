from ldotcommons import (sqlalchemy as ldotsa, utils)


# Probabily there is a better solution for this inmutable dict
class Query(dict):
    _ready = False

    def __init__(self, **params):
        def _glob_to_sa_like(params):
            ret = {}

            for (param, value) in params.items():
                if param.endswith('_like'):
                    value = ldotsa.glob_to_like(value)

                    if not value.startswith('%'):
                        value = '%' + value

                    if not value.endswith('%'):
                        value = value + '%'

                ret[param] = value

            return ret

        params = _glob_to_sa_like(params)

        if 'selector' not in params:
            params['selector'] = 'source'

        if 'language' in params:
            params['language'] = params['language'].lower()

        if 'type' in params:
            params['type'] = params['type'].lower()

        super(Query, self).__init__(**params)
        self._ready = True

    def pop(self, k, **kwargs):
        return self.__delitem__(k)

    def __setitem__(self, k, v):
        if self._ready:
            raise ValueError('Query objects are inmutable')
        else:
            super(dict, self).__setitem__(k, v)

    def __delitem__(self, k):
        raise ValueError('Query objects are inmutable')

    def __repr__(self):
        return '<Query {}>'.format(super(Query, self).__repr__())


class Selector:
    def __init__(self, app):
        self.app = app
        self._auto_import = self.app.settings.get('auto-import')

    def get_queries(self):
        cfg_dict = utils.configparser_to_dict(self.app.config)
        queries = utils.MultiDepthDict(cfg_dict).subdict('query')
        return {k: Query(**v) for (k, v) in queries.items()}

    def get_selector(self, query):
        if not isinstance(query, Query):
            raise ValueError('query is not a Query object')

        tmp = dict(query)
        selector_type = tmp.pop('selector')

        return self.app.get_extension(
            'selector', selector_type,
            query=tmp)

    def select(self, query, everything=False):
        if not isinstance(query, Query):
            raise ValueError('query must be a Query instance')

        if self._auto_import:
            self.app.importer.import_query(query)

        selector = self.get_selector(query)
        for src in selector.select(everything):
            yield src
