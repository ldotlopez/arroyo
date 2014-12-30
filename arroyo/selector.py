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

        super(Query, self).__init__(**params)
        self._ready = True

    def __setitem__(self, k, v):
        if self._ready:
            raise ValueError('Query objects are inmutable')
        else:
            super(dict, self).__setitem__(k, v)

    def __delitem__(self, k):
        raise ValueError('Query objects are inmutable')


class Selector:
    def __init__(self, app):
        self.app = app

    def get_queries(self):
        cfg_dict = utils.configparser_to_dict(self.app.config)
        queries = utils.MultiDepthDict(cfg_dict).subdict('query')
        return {k: Query(**v) for (k, v) in queries.items()}

    def get_selector(self, query):
        selector_name = query.pop('selector', 'source')
        return self.app.get_implementation('selector', selector_name)()

    def select(self, query, download=False):
        if not isinstance(query, Query):
            raise ValueError('query must be a Query instance')

        # FIXME: selector API is a bit redundant
        # The following block is equivalent to:
        # > self.get_selector(query).select(**query)
        # where the second query parameter is redundant.
        # That operation must be rework to the following one:
        # > self.get_selector(query).select()

        selector = self.get_selector(query)
        for (src, data) in selector.select(**query):
            if download:
                self.app.downloader.add(src)
                selector.post_download(src, data)
            yield src
