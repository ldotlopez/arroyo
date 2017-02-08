# -*- coding: utf-8 -*-

import abc
import aiohttp
import asyncio
import enum
import itertools
import re
import sys
import traceback
from urllib import parse


from appkit import (
    logging,
    uritools,
    utils
)


import arroyo.exc
from arroyo import (
    downloads,
    kit,
    models
)


class Provider(kit.Extension):
    def __unicode__(self):
        return "Provider({name})".format(
            name=self.__extension_name__)

    __str__ = __unicode__

    @abc.abstractmethod
    def compatible_uri(self, uri):
        attr_name = 'URI_PATTERNS'
        attr = getattr(self, attr_name, None)

        if not (isinstance(attr, (list, tuple)) and len(attr)):
            msg = "Class {cls} must override {attr} attribute"
            msg = msg.format(self=self.__class__.__name__, attr=attr_name)
            raise NotImplementedError(msg)

        RegexType = type(re.compile(r''))
        for pattern in attr:
            if isinstance(pattern, RegexType):
                if pattern.search(uri):
                    return True
            else:
                if re.search(pattern, uri):
                    return True

        return False

    @abc.abstractmethod
    def paginate(self, uri):
        yield uri

    @abc.abstractmethod
    def get_query_uri(self, query):
        return None

    @abc.abstractmethod
    def fetch(self, fetcher, uri):
        return (yield from fetcher.fetch(uri))

    @abc.abstractmethod
    def parse(self, buffer, parser):
        msg = "Provider {name} doesn't implement parse method"
        msg = msg.format(name=self.__extension_name__)
        raise NotImplementedError(msg)


class Origin:
    def __init__(self, provider, display_name=None, uri=None, iterations=1,
                 overrides={}, logger=None):

        if not isinstance(provider, Provider):
            msg = "Invalid provider"
            msg = msg.format(name=nme, value=var)
            raise TypeError(msg)

        uri = uri or provider.DEFAULT_URI

        # Check strs
        strs = [
            ('display_name', display_name, True),
            ('uri', uri, True),
        ]

        for (nme, var, nullable) in strs:
            if var is None and nullable:
                continue

            if isinstance(var, str) and var != '':
                continue

            msg = "Invalid value '{value}' for '{name}'. It must be a str"
            msg = msg.format(name=nme, value=var)
            raise TypeError(msg)

        # Check ints
        if not isinstance(iterations, int):
            msg = "Invalid value '{value}' for '{name}'. It must be an int"
            msg = msg.format(name='iterations', value=iterations)
            raise TypeError(msg)

        # Check overrides
        if not all([isinstance(k, str) and k != ''
                    for k in overrides]):
            msg = "Override keys must be non-empty strings"
            raise TypeError(msg)

        for k in ['type', 'language']:
            if k in overrides:
                if not isinstance(overrides[k], str) or str == '':
                    msg = "override key '{key}' must be a non-empty string"
                    msg = msg.format(key=k)
                    raise TypeError(msg)

        self.provider = provider
        self.display_name = display_name
        self.uri = uritools.normalize(uri)
        self.iterations = iterations
        self.overrides = overrides.copy()
        self.logger = logger or logging.getLogger('{}-origin'.format(
            provider.__extension_name__))

    def __unicode__(self):
        return 'Origin({provider})'.format(
            name=self.provider.__extension_name__)

    def __str__(self):
        return self.__unicode__()

    def __repr__(self):
        return '<arroyo.importer.Origin ({name}) object at {hexid}>'.format(
            name=self.provider.__extension_name__,
            hexid=hex(id(self)))


class Importer:
    def __init__(self, app, logger=None):
        self.app = app
        self.logger = logger or logging.getLogger('importer')

        app.signals.register('source-added')
        app.signals.register('source-updated')
        app.signals.register('sources-added-batch')
        app.signals.register('sources-updated-batch')
        app.register_extension_point(Provider)
        app.register_extension_class(ImporterCronTask)

    def _settings_validator(self, key, value):
        """Validates settings"""
        return value

    def origin_from_params(self, display_name=None, provider=None, uri=None,
                           iterations=1, language=None, type=None):
        extension = None

        if not provider and not uri:
            msg = "Neither provider or uri was provided"
            raise TypeError(msg)

        if provider:
            # Get extension from provider
            extension = self.app.get_extension(Provider, provider)
            uri = uritools.normalize(uri or extension.DEFAULT_URI)

        else:
            # Get extension from uri
            uri = uritools.normalize(uri)
            for (name, ext) in self.app.get_extensions_for(Provider):
                if ext.compatible_uri(uri):
                    extension = ext
                    msg = "Found compatible provider for {uri}: {provider}"
                    msg = msg.format(
                        uri=uri,
                        provider=extension.__extension_name__)
                    self.app.logger.debug(msg)
                    break

        if not extension:
            msg = ("No provider plugin is compatible with '{uri}'. "
                   "Fallback to generic")
            msg = msg.format(uri=uri)
            self.logger.warning(msg)
            extension = self.app.get_extension(Provider, 'generic')

        overrides = {}
        if language:
            overrides['language'] = language
        if type:
            overrides['type'] = type

        return Origin(display_name=display_name, provider=extension, uri=uri,
                      iterations=iterations, overrides=overrides)

    def get_configured_origins(self):
        specs = self.app.settings.get('origin', default={})
        if not specs:
            msg = "No origins defined"
            self.app.logger.warning(msg)
            return []

        return [self.origin_from_params(display_name=name, **params)
                for (name, params) in specs.items()]

    @asyncio.coroutine
    def get_buffer_from_uri(self, origin, uri):
        try:
            res = yield from origin.provider.fetch(self.app.fetcher, uri)

        except (asyncio.CancelledError,
                asyncio.TimeoutError,
                aiohttp.errors.ClientOSError,
                aiohttp.errors.ClientResponseError,
                aiohttp.errors.ServerDisconnectedError) as e:
            msg = "Error fetching «{uri}»: {msg}"
            msg = msg.format(
                uri=uri, type=e.__class__.__name__,
                msg=str(e) or 'no reason')
            self.logger.error(msg)
            res = e

        except Exception as e:
            print(traceback.format_exc(), file=sys.stderr)
            msg = "Unhandled exception {type}: {e}"
            msg = msg.format(type=type(e), e=e)
            self.logger.critical(msg)
            res = e

        if not isinstance(res, Exception) and (res is None or res == ''):
            msg = "Empty or None buffer for «{uri}»"
            msg = msg.format(uri=uri)
            self.logger.error(msg)

        return (origin, uri, res)

    @asyncio.coroutine
    def get_buffers_from_origin(self, origin):
        g = origin.provider.paginate(origin.uri)
        iterations = max(1, origin.iterations)

        # Generator can raise StopIteration before iterations is reached
        # We use a for loop instead to catch gracefully this situation
        tasks = []
        for i in range(iterations):
            try:
                uri = next(g)
                tasks.append(self.get_buffer_from_uri(origin, uri))
            except StopIteration:
                msg = ("{provider} has stopped the pagination after "
                       "iteration #{index}")
                msg = msg.format(provider=origin.provider, index=i)
                self.logger.warning(msg)
                break

        ret = yield from asyncio.gather(*tasks)
        return ret

    def get_data_from_origin(self, *origins):
        results = []

        @asyncio.coroutine
        def collect(origin):
            res = yield from self.get_buffers_from_origin(origin)
            results.extend(res)

        tasks = [collect(o) for o in origins]
        loop = asyncio.get_event_loop()
        loop.run_until_complete(asyncio.gather(*tasks))

        parser = self.app.settings.get('importer.parser')
        data = []
        for (origin, uri, res) in results:
            if isinstance(res, Exception) or res is None or res == '':
                continue

            try:
                res = origin.provider.parse(res, parser=parser)

            except arroyo.exc.OriginParseError as e:
                msg = "Error parsing «{uri}»: {e}"
                msg = msg.format(uri=uri, e=e)
                self.logger.error(msg)
                continue

            except Exception as e:
                print(traceback.format_exc(), file=sys.stderr)
                msg = "Unhandled exception {type}: {e}"
                msg = msg.format(type=type(e), e=e)
                self.logger.critical(msg)
                continue

            if res is None:
                msg = ("Incorrect API usage in {origin}, return None is not "
                       "allowed. Raise an Exception or return [] if no "
                       "sources are found")
                msg = msg.format(origin=origin)
                self.logger.critical(msg)
                continue

            if not isinstance(res, list):
                msg = "Invalid data type for URI «{uri}»: '{type}'"
                msg = msg.format(uri=uri, type=res.__class__.__name__)
                self.logger.critical(msg)
                continue

            if len(res) == 0:
                msg = "No sources found in «{uri}»"
                msg = msg.format(uri=uri)
                self.logger.warning(msg)
                continue

            res = self.normalize_source_data(origin, *res)
            data.extend(res)

            msg = "{n} sources found at {uri}"
            msg = msg.format(n=len(res), uri=uri)
            self.logger.info(msg)

        return data

    def process(self, *origins):
        data = self.get_data_from_origin(*origins)
        return self.process_source_data(*data)

    def normalize_source_data(self, origin, *psrcs):
        required_keys = set([
            'name',
            'provider',
            'uri',
        ])
        allowed_keys = required_keys.union(set([
            'created',
            'language',
            'leechers',
            'meta',
            'seeds',
            'size',
            'type'
        ]))

        ret = []
        now = utils.now_timestamp()

        for psrc in psrcs:
            if not isinstance(psrc, dict):
                msg = "Origin «{name}» emits invalid data type: {datatype}"
                msg = msg.format(name=origin.provider.__extension_name__,
                                 datatype=str(type(psrc)))
                self.logger.error(msg)
                continue

            # Insert provider name
            psrc['provider'] = origin.provider.__extension_name__

            # Apply overrides
            psrc.update(origin.overrides)

            # Check required keys
            missing_keys = required_keys - set(psrc.keys())
            if missing_keys:
                msg = ("Origin «{name}» doesn't provide the required "
                       "following keys: {missing_keys}")
                msg = msg.format(name=origin.provider.__extension_name__,
                                 missing_keys=missing_keys)
                self.logger.error(msg)
                continue

            # Only those keys are allowed
            forbiden_keys = [k for k in psrc if k not in allowed_keys]
            if forbiden_keys:
                msg = ("Origin «{name}» emits the following invalid "
                       "properties for its sources: {forbiden_keys}")
                msg = msg.format(name=psrc['provider'],
                                 forbiden_keys=forbiden_keys)
                self.logger.warning(msg)

            psrc = {k: psrc.get(k, None) for k in allowed_keys}

            # Check value types
            checks = [
                ('created', int),
                ('leechers', int),
                ('name', str),
                ('seeds', int),
                ('size', int),
                ('permalink', str),
                ('uri', str),
            ]
            for k, kt in checks:
                if (psrc.get(k) is not None) and (not isinstance(psrc[k], kt)):
                    try:
                        psrc[k] = kt(psrc[k])
                    except (TypeError, ValueError):
                        msg = ("Origin «{name}» emits invalid «{key}» value. "
                               "Expected {expectedtype} (or compatible), got "
                               "{currtype}")
                        msg = msg.format(
                            name=origin.provider.__extension_name__,
                            key=k,
                            expectedtype=kt,
                            currtype=str(type(psrc[k])))
                        self.logger.error(msg)
                        continue

            psrc['meta'] = psrc.get('meta', {})
            if psrc['meta']:
                if not all([isinstance(k, str) and isinstance(v, str)
                            for (k, v) in psrc['meta'].items()]):
                        msg = ("Origin «{name}» emits invalid «meta» "
                               "value. Expected dict(str->str)")
                        msg = msg.format(name=self.provider)
                        self.logger.warning(msg)
                        psrc['meta'] = {}

            # Calculate URN from uri. If not found its a lazy source
            # IMPORTANT: URN is **lowercased** and **sha1-encoded**
            try:
                qs = parse.urlparse(psrc['uri']).query
                urn = parse.parse_qs(qs)['xt'][-1]
                urn = urn.lower()
                sha1urn, b64urn = downloads.calculate_urns(urn)
                psrc['urn'] = sha1urn
            except KeyError:
                pass

            # Fix created
            psrc['created'] = psrc.get('created', None) or now

            # Set discriminator
            psrc['_discriminator'] = psrc.get('urn') or psrc.get('uri')
            assert(psrc['_discriminator'] is not None)

            # Append to ret value
            ret.append(psrc)

        return ret

    def process_source_data(self, *data):
        psources_data = self._process_remove_duplicates(data)
        contexts = self._process_create_contexts(psources_data)
        self._process_insert_existing_sources(contexts)
        self._process_update_existing_sources(contexts)
        self._process_insert_new_sources(contexts)

        return self._process_finalize(contexts)

    def resolve_source(self, source):
        def _update_source(data):
            keys = 'language leechers seeds size type uri urn'.split()
            for k in keys:
                if k in data:
                    setattr(source, k, data[k])

        origin = Origin(
            provider=self.app.get_extension(Provider, source.provider),
            uri=source.uri)

        data = self.get_data_from_origin(origin)
        data = self._process_remove_duplicates(data)
        contexts = self._process_create_contexts(data)
        self._process_insert_existing_sources(contexts)

        # Insert original source into context
        for ctx in contexts:
            if ctx.data['name'] == source.name:
                ctx.source = source
                continue

        self._process_update_existing_sources(contexts)
        self._process_insert_new_sources(contexts)
        self._process_finalize(contexts)

        if not source.urn:
            raise arroyo.exc.SourceResolveError(source)

        return source

    def run(self):
        origins = self.get_configured_origins()
        return self.process(*origins)

    def _process_remove_duplicates(self, psources):
        ret = dict()

        for psrc in psources:
            key = psrc['_discriminator']
            assert key is not None

            # Keep the most recent if case of duplicated
            if key not in ret or psrc['created'] > ret[key]['created']:
                ret[key] = psrc

        return list(ret.values())

    def _process_create_contexts(self, psources):
        ret = []
        for psrc in psources:
            discriminator = psrc.pop('_discriminator')
            assert discriminator is not None

            meta = psrc.pop('meta', {})
            ret.append(ProcessingState(
                data=psrc,
                discriminator=discriminator,
                meta=meta,
                source=None,
                tags=[]
            ))

        return ret

    def _process_insert_existing_sources(self, contexts):
        # Check there is any context because the in_ below
        # warns about empty 'in' clauses
        if not contexts:
            return

        table = {ctx.discriminator: ctx for ctx in contexts}
        existing = self.app.db.session.query(models.Source).filter(
            models.Source._discriminator.in_(table.keys())
        ).all()

        for src in existing:
            table[src._discriminator].source = src

    def _process_update_existing_sources(self, contexts):
        for ctx in contexts:
            updated = False

            if ctx.source is None:
                continue

            if ctx.source.name != ctx.data['name']:
                updated = True
                ctx.tags.append(ProcessingTag.NAME_UPDATED)

            # Override srcs's properties with src_data properties
            for key in ctx.data:
                if key == '_discriminator':
                    continue

                # …except for 'created'
                # Some origins report created timestamps from heuristics,
                # variable or fuzzy data that is degraded over time.
                # For these reason we keep the first 'created' data as the
                # most fiable
                if key == 'created' and \
                   ctx.source.created is not None and \
                   ctx.source.created < ctx.data['created']:
                    continue

                if getattr(ctx.source, key) != ctx.data[key]:
                    updated = True
                    setattr(ctx.source, key, ctx.data[key])

            if updated:
                ctx.tags.append(ProcessingTag.UPDATED)

    def _process_insert_new_sources(self, contexts):
        for ctx in contexts:
            if ctx.source is not None:
                continue

            ctx.source = models.Source.from_data(**ctx.data)
            ctx.tags.append(ProcessingTag.ADDED)

    # With all data prepared we can process it
    def _process_finalize(self, contexts):
        added = []
        updated = []
        name_updated = []

        for ctx in contexts:
            if ProcessingTag.ADDED in ctx.tags:
                added.append(ctx.source)

            if ProcessingTag.NAME_UPDATED in ctx.tags:
                name_updated.append(ctx.source)

            if ProcessingTag.UPDATED in ctx.tags:
                updated.append(ctx.source)

        mediainfo_sources = added + name_updated

        sources_and_metas = [(ctx.source, ctx.meta) for ctx in contexts]
        self.app.mediainfo.process(*sources_and_metas)

        self.app.db.session.add_all(added)
        self.app.db.session.commit()

        self.app.signals.send('sources-added-batch', sources=added)
        self.app.signals.send('sources-updated-batch',
                              sources=name_updated + updated)

        msg = '{n} sources {action}'
        self.app.logger.info(msg.format(n=len(added),
                                        action='added'))
        self.app.logger.info(msg.format(n=len(updated),
                                        action='updated'))
        self.app.logger.info(msg.format(n=len(set(added+name_updated)),
                                        action='parsed'))

        ret = [ctx.source for ctx in contexts]
        return ret


class ProcessingState:
    def __init__(self, data=None, discriminator=None, meta=None, source=None,
                 tags=None):
        self.data = data or {}
        self.discriminator = discriminator
        self.meta = meta or {}
        self.source = source
        self.tags = tags or []

    def __repr__(self):
        internals = (
            "data={data},discriminator={discriminator},meta={meta},"
            "source={source},tags={tags}"
        ).format(
            data=repr(self.data), discriminator=self.discriminator,
            meta=repr(self.meta), source=repr(self.source),
            tags=repr(self.tags)
        )

        base = "<arroyo.importer.ProcessingState({internals}) object at {id}>"
        return base.format(internals=internals, id=hex(id(self)))


class ProcessingTag(enum.Enum):
    ADDED = 1
    UPDATED = 2
    NAME_UPDATED = 3


class ImporterCronTask(kit.Task):
    __extension_name__ = 'importer'
    INTERVAL = '3H'

    def execute(self):
        self.app.importer.run()
