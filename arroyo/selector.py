# -*- coding: utf-8 -*-

import abc
import collections
import functools
import itertools
import types


from appkit import logging


import arroyo.exc
from arroyo import (
    coretypes,
    importer,
    kit,
    mediainfo,
    models,
)


class FilterNotFoundError(Exception):
    pass


class FilterCollissionError(Exception):
    pass


class Selector:
    def __init__(self, app):
        self.app = app
        self.logger = logging.getLogger('selector')
        self.app.register_extension_point(Filter)
        self.app.register_extension_point(Sorter)

    def _query_params_from_keyword(self, keyword, type_hint=None):
        try:
            entity, metadata = mediainfo.parse(
                keyword, type_hint=type_hint)
            keyword_params = {
                key: str(value)
                for (key, value) in entity.items()
                if value
            }

        except mediainfo.ParseError as e:
            words = keyword.lower().split()
            words = [x.strip() for x in words]
            words = [x for x in words if x]

            keyword_params = {
                'name-glob': '*' + '*'.join(words) + '*'
            }
            metadata = {}

        # FIXME: Add 'reverse' matching HANDLERS to Filter extension
        # Keep in sync with filters from arroyo.plugins.filters.mediainfo
        reverse_filters = [
            (mediainfo.Tags.VIDEO_CODEC, 'codec'),
            (mediainfo.Tags.MEDIA_CONTAINER, 'container'),
            (mediainfo.Tags.MIMETYPE, 'mimetype'),
            (mediainfo.Tags.RELEASE_GROUP, 'release-group'),
            (mediainfo.Tags.VIDEO_CODEC, 'codec'),
            (mediainfo.Tags.VIDEO_FORMAT, 'format'),
            (mediainfo.Tags.VIDEO_SCREEN_SIZE, 'quality'),
        ]

        metadata_params = {
            param: metadata[mediainfo_tag]
            for (mediainfo_tag, param) in reverse_filters
            if mediainfo_tag in metadata
        }

        params = {}
        params.update(metadata_params)
        params.update(keyword_params)

        return params

    def _default_query_params_from_config(self, type):
        assert isinstance(type, str) and type

        query_defalts = self.app.settings.get(
            'selector.query-defaults',
            default={})
        type_defaults = self.app.settings.get(
            'selector.query-{type}-defaults'.format(type=type),
            default={})

        params_ = {}
        params_.update(query_defalts)
        params_.update(type_defaults)

        return params_

    def query_from_args(self, keyword=None, params=None):
        if params is None:
            params = {}

        if keyword:
            keyword_params = self._query_params_from_keyword(
                keyword, params.get('type'))
        else:
            keyword_params = {}

        default_params = self._default_query_params_from_config(
            params.get('type') or keyword_params.get('type') or 'source')

        params_ = {}
        params_.update(default_params)
        params_.update(keyword_params)
        params_.update(params)

        # FIXME: Deprecation code
        if 'kind' in params_:
            msg = "'kind' parameter is deprecated. Use 'type'"
            self.logger.warning(msg)
            params_['type'] = params_.pop('kind')

        return coretypes.Query(**params_)

    def queries_from_config(self):
        specs = self.app.settings.get('query', default={})
        if not specs:
            msg = "No queries defined"
            self.logger.warning(msg)
            return []

        ret = {name: self.query_from_args(
            keyword=None,
            params=params
        ) for (name, params) in specs.items()}

        return ret

    def _get_filter_registry(self):
        registry = {}

        # Build filter register
        # This register a is two-level dict. First by model, second by key
        for (name, ext) in self.app.get_extensions_for(Filter):
            if ext.APPLIES_TO not in registry:
                registry[ext.APPLIES_TO] = {}

            for handler in ext.HANDLES:
                if handler in registry[ext.APPLIES_TO]:
                    msg = ("Filter {model}:{handler} from {extension} already "
                           "defined by {existing_extension}")
                    msg = msg.format(
                        model=ext.APPLIES_TO, extension=ext,
                        existing_extension=registry[ext.APPLIES_TO][handler])
                    raise FilterCollissionError(msg)

                registry[ext.APPLIES_TO][handler] = ext

        return registry

    def matches(self, query, auto_import=None):
        def _count(x):
            try:
                return len(x)
            except TypeError:
                return x.count()

        if not isinstance(query, coretypes.BaseQuery):
            raise TypeError('query is not a Query')

        self.maybe_run_importer_process(query, auto_import)

        debug = self.app.settings.get('log-level').lower() == 'debug'

        msg = "Search matches for query: {query}"
        msg = msg.format(query=repr(query))
        self.logger.debug(msg)

        # Get base query set from query
        qs = self.app.db.session.query(models.Source)
        if isinstance(query, coretypes.SourceQuery):
            pass
        elif isinstance(query, coretypes.EpisodeQuery):
            qs = qs.join(models.Episode)
        elif isinstance(query, coretypes.MovieQuery):
            qs = qs.join(models.Movie)
        else:
            raise ValueError(query)

        # qs = query.get_query(self.app.db.session)
        qs_models = itertools.chain(qs._entities, qs._join_entities)
        qs_models = [x.mapper.class_ for x in qs_models]

        # Get filters
        qs_funcs, iter_funcs = \
            self.filters_for_query(qs_models, query)

        unrolled = False

        ret = qs

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
                ret = (x for x in ret)
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
                self.logger.debug(msg)

        if not unrolled:
            ret = list(ret)

        return ret

    def filters_for_query(self, qs_models, query):
        if not isinstance(query, coretypes.BaseQuery):
            raise TypeError('Expected Query object')

        if not isinstance(qs_models, list):
            raise TypeError('qs_models should be a list of models')

        # qs_models = set([models.Source])

        # if isinstance(query, EpisodeQuery):
        #     qs_models.add(models.Episode)

        # elif isinstance(query, MovieQuery):
        #     qs_models.add(models.Movie)

        # else:
        #     raise ValueError(query)

        registry = self._get_filter_registry()

        iter_filters = []
        qs_filters = []

        for (key, value) in query.items():
            ext = None
            for model in qs_models:
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
                msg = "Unable to find matching filter for «{key}»"
                msg = msg.format(key=key)
                raise FilterNotFoundError(msg)

        return qs_filters, iter_filters

    def group(self, sources):
        def _entity_key_func(src):
            if src.entity is None:
                return ('', src.id)
            else:
                return (src.entity.__class__.__name__, src.entity.id)

        def _entity_str_key_func(key, group):
            # key can be a source or an entity
            if isinstance(key, models.Source):
                type = ''
            else:
                type = key.__class__.__name__.lower()

            return (type, str(key).lower(), key.id)

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

        return groups

    def sort(self, sources):
        assert len(set([x.entity or x for x in sources])) <= 1

        sorter = self.app.get_extension(
            Sorter,
            self.app.settings.get('selector.sorter'))

        return sorter.sort(sources)

    def select(self, sources):
        if len(set([x.entity or x for x in sources])) != 1:
            msg = ("All sources must refer the same entity "
                   "(episode, movie, etc...)")
            raise ValueError(msg)

        if not sources:
            return None

        return next(self.sort(sources))

    def select_from_mixed_sources(self, sources):
        ret = []

        for (entity, sources) in self.group(sources):
            ret.append(self.select(sources))

        return ret

    def get_origins_for_query(self, query):
        """Get autogenerated origins for a selector.QuerySpec object.

        One query can produce zero or more or plugin.Origins from the activated
        origin extensions.

        Returned origins are configured with one iteration.
        """

        msg = "Discovering origins for {query}"
        msg = msg.format(query=query)
        self.logger.info(msg)

        exts = list(self.app.get_extensions_for(importer.Provider))

        if not exts:
            msg = ("There are no origin implementations available or none of "
                   "them is enabled, check your configuration")
            self.logger.warning(msg)
            return []

        exts_and_uris = []
        for (name, ext) in exts:
            uri = ext.get_query_uri(query)
            if uri:
                msg = " Found compatible origin '{name}'"
                msg = msg.format(name=name)
                self.logger.info(msg)
                exts_and_uris.append((ext, uri))

        if not exts_and_uris:
            msg = "No compatible origins found for {query}"
            msg = msg.format(query=query)
            self.logger.warning(msg)
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
