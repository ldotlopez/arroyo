# -*- coding: utf-8 -*-

import abc
import functools
import itertools
import sys
import types


import appkit.extensionmanager
import guessit


import arroyo.exc
from arroyo import (
    importer,
    kit,
    models,
)


class Query(kit.Extension):
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

    def asdict(self):
        return self.params.copy()

    @property
    def base_string(self):
        return self._get_base_string()

    def _get_base_string(self, base_key='name'):
        ret = None

        if base_key in self.params:
            ret = self.params[base_key]

        elif base_key+'-glob' in self.params:
            ret = self.params[base_key+'-glob'].replace('*', ' ')
            ret = ret.replace('.', ' ')

        elif base_key+'-like' in self.params:
            ret = self.params[base_key+'-like'].replace('%', ' ')
            ret = ret.replace('_', ' ')

        return ret.strip() if ret else None

    def get_query_set(self, session, include_all=False):
        raise NotImplementedError()

    @property
    def kind(self):
        if self.KIND is None:
            msg = "Class {clsname} must override KIND attribute"
            msg = msg.format(clsname=self.__class__.__name__)
            raise NotImplementedError(msg)

        return self.KIND

    def __eq__(self, other):
        return isinstance(other, Query) and self.asdict() == other.asdict()

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
        self.app.register_extension_point(Filter)
        self.app.register_extension_point(Query)
        self.app.register_extension_point(Sorter)

    def get_query_from_string(self, string, type_hint=None):
        def get_episode(info):
            assert info['type'] == 'episode'

            confident = (
                'title' in info and
                'season' in info and
                'episode' in info)

            return confident, dict(
                series=info.get('title', None),
                year=info.get('year', None),
                season=info.get('season', None),
                episode=info.get('episode', None),
                quality=info.get('screen_size', None),
                codec=info.get('video_codec', None)
            )

        def get_movie(info):
            assert info['type'] == 'movie'

            confident = (
                'title' in info and
                'year' in info)

            return confident, dict(
                title=info.get('title', None),
                year=info.get('year', None),
                quality=info.get('screen_size', None),
                codec=info.get('video_codec', None)
            )

        def get_source(string):
            words = string.lower().split()
            words = [x.strip() for x in words]
            words = [x for x in words if x]
            return True, {
                'name-glob': '*' + '*'.join(words) + '*'
            }

        guessed_info = guessit.guessit(string, options={'type': type_hint})

        kind = guessed_info['type']

        if kind == 'movie':
            confident, info = get_movie(guessed_info)
        elif kind == 'episode':
            confident, info = get_episode(guessed_info)
        else:
            confident, info = get_source(string)

        if type_hint:
            confident = True

        if not confident:
            kind = None
            dummy, info = get_source(string)

        info = {k: v for (k, v) in info.items() if v}
        info['kind'] = kind or 'source'

        return self.get_query_from_params(params=info)

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

        try:
            return self.app.get_extension(
                Query, impl_name,
                params=params_,
                display_name=display_name
            )
        except appkit.extensionmanager.ExtensionNotFoundError as e:
            msg = "Invalid query kind: {kind}"
            msg = msg.format(kind=impl_name)
            raise ValueError(msg) from e  # FIXME: Use custom exception

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
        for (name, ext) in self.app.get_extensions_for(Filter):
            if ext.APPLIES_TO not in registry:
                registry[ext.APPLIES_TO] = {}

            ext_conflicts = set(registry[ext.APPLIES_TO]).intersection(
                set(ext.HANDLES))
            if ext_conflicts:
                conflicts = conflicts.union(ext_conflicts)
                msg = ('Filter «{name}» disabled. Conflicts in {model}: '
                       '{conflicts}')
                msg = msg.format(
                    name=name,
                    model=repr(ext.APPLIES_TO),
                    conflicts=','.join(list(ext_conflicts)))

                self.app.logger.warning(msg)
                continue

            # Update registry with impl
            registry[ext.APPLIES_TO].update({
                key: ext for key in ext.HANDLES})

        return registry, conflicts

    def matches(self, query, everything=False, auto_import=None):
        def _count(x):
            try:
                return len(x)
            except TypeError:
                return x.count()

        if not isinstance(query, Query):
            raise TypeError('query is not a Query')

        self.maybe_run_importer_process(query, auto_import)

        debug = self.app.settings.get('log-level').lower() == 'debug'

        msg = "Search matches for query: {query}"
        msg = msg.format(query=str(query.params))
        self.app.logger.debug(msg)

        # Get base query set from query
        qs = query.get_query_set(self.app.db.session, everything)
        models = itertools.chain(qs._entities, qs._join_entities)
        models = [x.mapper.class_ for x in models]

        # Get filters
        qs_funcs, iter_funcs, dummy, dummy = \
            self.get_filters_from_params(models, query.params)

        ret = qs
        unrolled = False

        for func in qs_funcs + iter_funcs:
            ext = func.func.__self__
            (key, value) = func.args

            # For debug logging level we have to do some ugly things
            if debug:
                if isinstance(ret, types.GeneratorType):
                    ret = list(ret)
                precount = _count(ret)

            # Check if we need to unroll result
            need_unroll = (
                unrolled and
                isinstance(ext, IterableFilter) and
                not isinstance(ret, collections.Iterable))
            if need_unroll:
                ret = (x for x in qs)
                unrolled = True

            ret = func(ret)

            if debug:
                if isinstance(ret, types.GeneratorType):
                    ret = list(ret)

                msg = ("Apply filter {name}({key}, {value}) over {precount} "
                       "items: {postcount} results")
                msg = msg.format(
                    name=ext.__extension_name__,
                    key=key,
                    value=value,
                    precount=precount,
                    postcount=_count(ret))
                self.app.logger.debug(msg)

        if not unrolled:
            ret = list(ret)

        return ret

    def get_filters_from_params(self, models, params):
        if not isinstance(models, list):
            raise TypeError('models should be a list of models')

        if not isinstance(params, dict):
            raise TypeError('params should be a dict <str:str>')

        registry, conflicts = self._get_filter_registry()

        iter_filters = []
        qs_filters = []
        missing = []

        for (key, value) in params.items():
            ext = None
            for model in models:
                if model not in registry or key not in registry[model]:
                    continue

                ext = registry[model][key]

                if isinstance(ext, QuerySetFilter):
                    qs_filters.append(functools.partial(
                        ext.alter, key, value))

                elif isinstance(ext, IterableFilter):
                    iter_filters.append(functools.partial(
                        ext.apply, key, value))

                else:
                    msg = "Unknow filter subclass {name}"
                    msg = msg.format(name=ext.__class__.__name__)
                    raise arroyo.exc.FatalError(msg)

            if ext is None:
                missing.append(key)

                msg = "Unable to find matching filter for «{key}»"
                msg = msg.format(key=key)
                raise arroyo.exc.FatalError(msg)

        return qs_filters, iter_filters, conflicts, missing

    def group(self, sources):
        def _entity_key_func(src):
            if src.entity is None:
                return ('', src.id)
            else:
                return (src.entity.__class__.__name__, src.entity.id)

        def _entity_str_key_func(key, group):
            # key can be a source or an entity

            if isinstance(key, models.Source):
                kind = ''
            else:
                kind = key.__class__.__name__.lower()

            return (kind, str(key).lower(), key.id)

        # Before group anything we need to sort data
        sources = sorted(sources,
                         key=lambda x: _entity_key_func(x))

        sources = list(sources)

        # The group sources by entity or by itself
        groups = itertools.groupby(sources,
                                   lambda x: x.entity or x)

        # Unfold groups
        groups = ((grp, list(srcs)) for (grp, srcs) in groups)
        groups = list(groups)

        # Order by entity and entity as a str
        groups = sorted(
            groups,
            key=lambda x: _entity_str_key_func(*x))
        groups = list(groups)

        yield from groups

    def sort(self, sources):
        assert len(set([x.entity or x for x in sources])) <= 1

        sorter = self.app.get_extension(
            Sorter,
            self.app.settings.get('selector.sorter'))

        return sorter.sort(sources)

    def select(self, sources):
        assert len(set([x.entity or x for x in sources])) <= 1

        return next(self.sort(sources))

    # def select_one_foreach_group(self, sources):
    #     yield from (
    #         (common, self.select(sources))
    #         for (common, sources) in self.group(sources))

    def get_origins_for_query(self, query):
        """Get autogenerated origins for a selector.QuerySpec object.

        One query can produce zero or more or plugin.Origins from the activated
        origin extensions.

        Returned origins are configured with one iteration.
        """

        msg = "Discovering origins for {query}"
        msg = msg.format(query=query)
        self.app.logger.info(msg)

        exts = list(self.app.get_extensions_for(importer.Provider))

        if not exts:
            msg = ("There are no origin implementations available or none of "
                   "them is enabled, check your configuration")
            self.app.logger.warning(msg)
            return []

        exts_and_uris = []
        for (name, ext) in exts:
            uri = ext.get_query_uri(query)
            if uri:
                msg = " Found compatible origin '{name}'"
                msg = msg.format(name=name)
                self.app.logger.info(msg)
                exts_and_uris.append((ext, uri))

        if not exts_and_uris:
            msg = "No compatible origins found for {query}"
            msg = msg.format(query=query)
            self.app.logger.warning(msg)
            return []

        origins = [importer.Origin(p, uri=uri) for (p, uri) in exts_and_uris]
        return origins

    def maybe_run_importer_process(self, query, value=None):
        if value is None:
            configured_origins = self.app.importer.get_configured_origins()
            value = not configured_origins

        if value:
            origins = self.get_origins_for_query(query)
            self.app.importer.process(*origins)


class Filter(kit.Extension):
    HANDLES = []  # keys
    APPLIES_TO = None  # model


class IterableFilter(Filter):
    @abc.abstractmethod
    def filter(self, key, value, item):
        raise NotImplementedError()

    def apply(self, key, value, iterable):
        return (x for x in iterable if self.filter(key, value, x))


class QuerySetFilter(Filter):
    @abc.abstractmethod
    def alter(self, key, value, qs):
        raise NotImplementedError()


class Sorter(kit.Extension):
    @abc.abstractmethod
    def sort(self, sources):
        return sources
