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

    def select(self, query):
        if not isinstance(query, Query):
            raise ValueError('query must be a Query instance')

        selector = self.get_selector(query)
        return selector.select(None, **query)

    # def _select(self, filters, all_states=False):
    #     def _glob_to_sa_like(query_params):
    #         ret = {}

    #         for (param, value) in query_params.items():
    #             if param.endswith('_like'):
    #                 value = ldotsa.glob_to_like(value)

    #                 if not value.startswith('%'):
    #                     value = '%' + value

    #                 if not value.endswith('%'):
    #                     value = value + '%'

    #             ret[param] = value

    #         return ret

    #     if not filters:
    #         raise ValueError('At least one filter is needed')

    #     if not isinstance(filters, dict):
    #         raise ValueError('Filters must be a dictionary')

    #     if not isinstance(all_states, bool):
    #         raise ValueError('all_states parameter must be a bool')

    #     filters = _glob_to_sa_like(filters)

    #     filter_impls = self.app.get_all('filter')
    #     query = self.app.db.session.query(models.Source)

    #     for (key, value) in filters.items():
    #         filter_impl = None
    #         for f_i in filter_impls:
    #             if key in f_i.handles:
    #                 filter_impl = f_i
    #                 break

    #         if filter_impl is None:
    #             msg = "filter {filter} is not recognized"
    #             _logger.warning(msg.format(filter=key))
    #             continue

    #         query = filter_impl.filter(query, key, value)

    #     if not all_states:
    #         query = query.filter(models.Source.state == models.Source.State.NONE)

    #     return query
