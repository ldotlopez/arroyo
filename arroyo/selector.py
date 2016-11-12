# -*- coding: utf-8 -*-

import itertools
import sys


from ldotcommons import utils


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

    def get_filters_from_params(self, params={}):
        reg = {}
        conflicts = {}

        # Build filter register
        for (name, impl) in self.app.get_implementations(Filter).items():
            impl_conflicts = set(reg).intersection(set(impl.HANDLES))
            if impl_conflicts:
                conflicts = conflicts.union(impl_conflicts)

                msg = 'Filter «{name}» disabled. Conflicts: {conflicts}'
                msg = msg.format(
                    name=name,
                    conflicts=','.join(list(conflicts)))
                self.app.logger.warning(msg)

                continue

            reg.update({x: impl for x in impl.HANDLES})

        # Instantiate filters
        filters = [reg[key](self.app, key, value)
                   for (key, value) in params.items()]

        missing = set(params) - set(reg)
        if missing:
            msg = "Unknow filters: {missing}"
            msg = msg.format(missing=','.join(list(conflicts)))
            self.app.logger.warning(msg)

        return filters, conflicts, missing

    def _classify_filters(self, filters):
        sql_based = {True: [], False: []}

        for f in filters:
            test = f.__class__.alter_query != Filter.alter_query
            sql_based[test].append(f)

        return sql_based[True], sql_based[False]

    def matches(self, query, everything=False):
        if not isinstance(query, Query):
            raise TypeError('query is not a Query')

        msg = "Search matches for query: {query}"
        msg = msg.format(query=str(query.params))
        self.app.logger.debug(msg)

        self._auto_import(query)

        # Get filters for those params
        filters, dummy, dummy = self.get_filters_from_params(query.params)

        # Split filters
        sql_based, iterable_based = self._classify_filters(filters)

        # Get base query set from query
        qs = query.get_query_set(self.app.db.session, everything)

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

        # Filter by SQL
        for f in sql_based:
            qs = f.alter_query(qs)
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

    def filter(self, x):
        raise NotImplementedError()

    def apply(self, iterable):
        return filter(self.filter, iterable)

    def alter_query(self, qs):
        raise NotImplementedError()


class Sorter(extension.Extension):
    def sort(self, sources):
        return sources
