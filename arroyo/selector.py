# -*- coding: utf-8 -*-

import abc
import itertools
import sys


import arroyo.exc
from arroyo import (
    extension,
    importer
)


class Query(extension.Extension):
    KIND = None

    def __init__(self, app, params={}, display_name=None):

        def _normalize_key(key):
            for x in [' ', '_']:
                key = key.replace(x, '-')
            return key

        if not isinstance(params, dict) or not dict:
            raise TypeError("params must be a non empty dict")

        params = {_normalize_key(k): v for (k, v) in params.items()}

        # FIXME: Remove this specific stuff out of here

        if 'language' in params:
            params['language'] = params['language'].lower()

        if 'type' in params:
            params['type'] = params['type'].lower()

        super().__init__(app)

        self.params = params
        self.display_name = display_name

    @property
    def base_string(self):
        return self._get_base_string()

    def _get_base_string(self, base_key='name'):
        if base_key in self.params:
            ret = self.params[base_key]

        elif base_key+'-glob' in self.params:
            ret = self.params[base_key+'-glob'].replace('*', ' ')
            ret = ret.replace('.', ' ')

        elif base_key+'-like' in self.params:
            ret = self.params[base_key+'-like'].replace('%', ' ')
            ret = ret.replace('_', ' ')

        return ret.strip()

    def get_query_set(self, session, include_all=False):
        raise NotImplementedError()

    @property
    def kind(self):
        if self.KIND is None:
            msg = "Class {clsname} must override KIND attribute"
            msg = msg.format(clsname=self.__class__.__name__)
            raise NotImplementedError(msg)

        return self.KIND

    def __repr__(self):
        if self.display_name:
            s = "'{name}', {params})".format(
                name=self.display_name, params=repr(self.params)
            )
        else:
            s = repr(self.params)

        return "{}({})".format(self.__class__.__name__, s)

    def __str__(self):
        return self.__unicode__()

    def __unicode__(self):
        return self.display_name or repr(self)


class Selector:
    def __init__(self, app):
        self.app = app

    def get_query_from_params(self, params={}, display_name=None):
        impl_name = params.pop('kind', 'source')

        query_defalts = self.app.settings.get(
            'selector.query-defaults',
            default={})
        kind_defaults = self.app.settings.get(
            'selector.query-{kind}-defaults'.format(kind=impl_name),
            default={})

        params_ = {}
        params_.update(query_defalts)
        params_.update(kind_defaults)
        params_.update(params)

        return self.app.get_extension(  # FIX: Handle exceptions
            Query, impl_name,
            params=params_,
            display_name=display_name
        )

    def get_configured_queries(self):
        specs = self.app.settings.get('query', default={})
        if not specs:
            msg = "No queries defined"
            self.app.logger.warning(msg)
            return []

        ret = [
            self.get_query_from_params(
                params=params, display_name=name
            )
            for (name, params) in specs.items()
        ]
        ret = [x for x in ret if x is not None]

        return ret

    def _get_filter_registry(self):
        registry = {}
        conflicts = set()

        # Build filter register
        # This register a is two-level dict. First by model, second by key
        for (name, impl) in self.app.get_implementations(Filter).items():

            if impl.APPLIES_TO not in registry:
                registry[impl.APPLIES_TO] = {}

            impl_conflicts = set(registry[impl.APPLIES_TO]).intersection(
                set(impl.HANDLES))
            if impl_conflicts:
                conflicts = conflicts.union(impl_conflicts)
                msg = ('Filter «{name}» disabled. Conflicts in {model}: '
                       '{conflicts}')
                msg = msg.format(
                    name=name,
                    model=repr(impl.APPLIES_TO),
                    conflicts=','.join(list(impl_conflicts)))

                self.app.logger.warning(msg)
                continue

            # Update registry with impl
            registry[impl.APPLIES_TO].update({
                key: impl for key in impl.HANDLES})

        return registry, conflicts

    def get_filters_from_params(self, models, params):
        if not isinstance(models, list):
            raise TypeError('models should be a list of models')

        if not isinstance(params, dict):
            raise TypeError('params should be a dict <str:str>')

        registry, conflicts = self._get_filter_registry()

        # Instantiate filters
        filters = []
        missing = []
        for (k, v) in params.items():
            f = None
            for m in models:
                if m not in registry or k not in registry[m]:
                    continue

                f = registry[m][k](self.app, k, v)
                filters.append(f)
                break

            if f is None:
                missing.append(k)

                msg = "Unable to find matching filter for «{key}»"
                msg = msg.format(key=k)
                raise arroyo.exc.FatalError(msg)

        return filters, conflicts, missing

    def _classify_filters(self, filters):
        sql_based = {True: [], False: []}

        for f in filters:
            test = isinstance(f, QuerySetFilter)
            sql_based[test].append(f)

        return sql_based[True], sql_based[False]

    def matches(self, query, everything=False):
        if not isinstance(query, Query):
            raise TypeError('query is not a Query')

        msg = "Search matches for query: {query}"
        msg = msg.format(query=str(query.params))
        self.app.logger.debug(msg)

        # Get base query set from query
        qs = query.get_query_set(self.app.db.session, everything)
        models = itertools.chain(qs._entities, qs._join_entities)
        models = [x.mapper.class_ for x in models]

        # Get filters for those params
        filters, dummy, dummy = self.get_filters_from_params(
            models, query.params)

        # Split filters
        sql_based, iterable_based = self._classify_filters(filters)

        # Do some debug
        debug = self.app.settings.get('log-level').lower() == 'debug'

        descs = itertools.chain(
            [('SQL', x) for x in sql_based],
            [('Iterable', x) for x in iterable_based]
        )

        for (typ, f) in descs:
            msg = "1. Discovered {type} filter: '{name}'"
            msg = msg.format(type=typ, name=f.__module__)
            self.app.logger.debug(msg)

        if debug:  # For optimation only count elements if user wants debug
            msg = "2. Initial element is count {count}"
            msg = msg.format(count=qs.count())
            self.app.logger.debug(msg)

        self._auto_import(query)

        # Filter by SQL
        for f in sql_based:
            qs = f.alter(qs)
            if debug:
                msg = ("After apply '{filter}({key}, {value})' "
                       "element count is {count}")
                msg = msg.format(
                    filter=f.__module__,
                    key=f.key, value=f.value,
                    count=qs.count())
                self.app.logger.debug(msg)

        items = list(qs)

        # Filter by iterable
        for f in iterable_based:
            items = f.apply(items)
            if debug:
                if not isinstance(items, list):
                    items = list(items)

                msg = ("3. After apply '{filter}({key}, {value})' "
                       "element count is {count}")
                msg = msg.format(
                    filter=f.__module__, count=len(items),
                    key=f.key, value=f.value)
                self.app.logger.debug(msg)

        return items

    def sort(self, matches):
        sorter = self.app.get_extension(
            Sorter,
            self.app.settings.get('selector.sorter'))

        return sorter.sort(matches)

    def select_single(self, matches):
        return next(self.sort(matches))

    def select(self, matches):
        def _entity_grouper(src):
            if src.type == 'episode':
                return "{}-{}-{}-{}".format(
                    src.episode.series.lower(),
                    src.episode.year or '-',
                    src.episode.season or '-',
                    src.episode.number or '-'
                )

            if src.type == 'movie':
                return "{}-{}".format(
                    src.movie.title.lower(),
                    src.movie.year or '-'
                )

            else:
                return src.entity

        # Sort matches by entity
        matches = sorted(
            matches,
            key=lambda x: -sys.maxsize
            if x.entity is None else x.entity.id)

        groups = itertools.groupby(matches, lambda src: _entity_grouper(src))
        for (entity, group) in groups:
            if entity is None:
                yield from group
            else:
                yield self.select_single(group)

    def get_origins_for_query(self, query):
        """Get autogenerated origins for a selector.QuerySpec object.

        One query can produce zero or more or plugin.Origins from the activated
        origin extensions.

        Returned origins are configured with one iteration.
        """

        msg = "Discovering origins for {query}"
        msg = msg.format(query=query)
        self.app.logger.info(msg)

        impls = self.app.get_implementations(importer.Origin)
        if not impls:
            msg = ("There are no origin implementations available or none of "
                   "them is enabled, check your configuration")
            self.app.logger.warning(msg)
            return []

        impls_and_uris = []
        for (name, impl) in impls.items():
            uri = impl(self.app).get_query_uri(query)
            if uri:
                msg = " Found compatible origin '{name}'"
                msg = msg.format(name=name)
                self.app.logger.info(msg)
                impls_and_uris.append((impl, uri))

        if not impls_and_uris:
            msg = "No compatible origins found for {query}"
            msg = msg.format(query=query)
            self.app.logger.warning(msg)
            return []

        origins = [impl(self.app, uri=uri) for (impl, uri) in impls_and_uris]
        return origins

    def _auto_import(self, query):
        if self.app.settings.get('auto-import'):
            origins = self.get_origins_for_query(query)
            self.app.importer.process(*origins)


class Filter(extension.Extension):
    HANDLES = ()

    def __init__(self, app, key, value):
        super().__init__(app)
        self.key = key
        self.value = value


class IterableFilter(Filter):
    @abc.abstractmethod
    def filter(self, x):
        raise NotImplementedError()

    def apply(self, iterable):
        return filter(self.filter, iterable)


class QuerySetFilter(Filter):
    @abc.abstractmethod
    def alter(self, qs):
        raise NotImplementedError()


class Sorter(extension.Extension):
    @abc.abstractmethod
    def sort(self, sources):
        return sources
