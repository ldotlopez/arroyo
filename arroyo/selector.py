# -*- coding: utf-8 -*-

import itertools
import sys


from ldotcommons import utils


import arroyo.exc
from arroyo import extension


class Selector:
    def __init__(self, app):
        self.app = app

    def get_queries_specs(self):
        return [QuerySpec(x, **params) for (x, params) in
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
        spec = QuerySpec(spec.name, **base)

        return self.app.get_extension(Query, spec.get('kind'), spec=spec)

    def _auto_import(self, query):
        if self.app.settings.get('auto-import'):
            self.app.importer.import_query_spec(query.spec)

    def matches(self, spec, everything=False):
        msg = "Search matches for spec: {spec}"
        msg = msg.format(spec=str(spec))
        self.app.logger.debug(msg)

        query = self.get_query_for_spec(spec)
        self._auto_import(query)
        ret = query.matches(everything)

        return sorted(
            ret,
            key=lambda x: -sys.maxsize
            if x.superitem is None else x.superitem.id)

    def sort(self, items):
        sorter = self.app.get_extension(
            Sorter,
            self.app.settings.get('selector.sorter', 'basic'))

        groups = itertools.groupby(items, lambda src: src.superitem)

        ret = []
        for (superitem, group) in groups:
            ret += list(sorter.sort(group))

        return ret

    def select(self, spec):
        sorter = self.app.get_extension(
            Sorter,
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

        for filtercls in self.app.get_implementations(Filter).values():
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
        debug = self.app.settings.get('log-level').lower() == 'debug'

        guessed_models = itertools.chain(qs._entities, qs._join_entities)
        guessed_models = [x.mapper.class_ for x in guessed_models]
        assert set(guessed_models) == set(models)

        filters = self.get_filters(guessed_models, params)

        missing = set(params).difference(set(filters))

        sql_aware = {True: [], False: []}
        for f in filters.values():
            test = f.__class__.alter_query != Filter.alter_query
            sql_aware[test].append(f)

        for x in sql_aware:
            filter_list = ', '.join([x.__module__ for x in sql_aware[x]])

            msg = ("{type} based filters: {filter_list}")
            msg = msg.format(type='SQL' if x else 'Python',
                             filter_list=filter_list or '[]')
            self.app.logger.debug(msg)

        if debug:
            msg = "Initial element is count {count}"
            msg = msg.format(count=qs.count())
            self.app.logger.debug(msg)

        for f in sql_aware.get(True, []):
            try:
                qs = f.alter_query(qs)
                if debug:
                    msg = "After apply '{filter}' element count is {count}"
                    msg = msg.format(filter=f.__module__, count=qs.count())
                    self.app.logger.debug(msg)

            except arroyo.exc.SettingError as e:
                msg = ("Ignoring invalid setting «{key}»: «{value}». "
                       "Filter discarted")
                msg = msg.format(key=e.key, value=e.value)
                self.app.logger.warning(msg)

        items = (x for x in qs)
        for f in sql_aware.get(False, []):
            items = f.apply(items)
            if debug:
                items = list(items)
                msg = "After apply '{filter}' element count is {count}"
                msg = msg.format(filter=f.__module__, count=len(items))
                self.app.logger.debug(msg)

        return items, missing


class Query(extension.Extension):
    def __init__(self, app, spec):
        super().__init__(app)
        self._spec = spec
        self.params = utils.InmutableDict(spec.exclude('kind'))

    @property
    def name(self):
        return self.spec.name

    @property
    def spec(self):
        return self._spec

    def matches(self, include_all=False):
        raise NotImplementedError()


class QuerySpec(utils.InmutableDict):
    def __init__(self, query_name, **kwargs):
        def _normalize_key(key):
            for x in [' ', '_']:
                key = key.replace(x, '-')
            return key

        kwargs = {_normalize_key(k): v for (k, v) in kwargs.items()}
        kwargs['kind'] = kwargs.get('kind', 'source')

        if 'language' in kwargs:
            kwargs['language'] = kwargs['language'].lower()

        if 'type' in kwargs:
            kwargs['type'] = kwargs['type'].lower()

        super().__init__(**kwargs)
        self._name = query_name

    @property
    def name(self):
        return self._name


class Filter(extension.Extension):
    HANDLES = ()

    @classmethod
    def compatible(cls, model, key):
        return model == cls.APPLIES_TO and key in cls.HANDLES

    def __init__(self, app, key, value):
        super().__init__(app)
        self.key = key
        self.value = value

    def filter(self, x):
        raise NotImplementedError()

    def apply(self, iterable):
        return filter(self.filter, iterable)

    def alter_query(self, qs):
        raise NotImplementedError()


class Sorter(extension.Extension):
    def sort(self, sources):
        return sources

    # def selection(self, matches):
    #     try:
    #         return matches[0]
    #     except IndexError:
    #         return None
