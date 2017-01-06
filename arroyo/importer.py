# -*- coding: utf-8 -*-

import abc
import aiohttp
import asyncio
import collections
import enum
import itertools
import json
import re
from urllib import parse


from ldotcommons import (
    logging,
    utils
)


from arroyo import (
    cron,
    downloads,
    exc,
    extension,
    models
)


class Importer:
    def __init__(self, app, logger=None):
        self.app = app
        self.logger = logger or logging.get_logger('importer')

        self._sched = None

        app.signals.register('source-added')
        app.signals.register('source-updated')
        app.signals.register('sources-added-batch')
        app.signals.register('sources-updated-batch')

        app.register_extension('import', ImporterCronTask)

    def _settings_validator(self, key, value):
        """Validates settings"""
        return value

    def origin_class_from_uri(self, uri):
        impls = self.app.get_implementations(Origin)

        for (name, impl) in impls.items():
            try:
                if impl.compatible_uri(uri):
                    return impl
            except NotImplementedError as e:
                self.app.logger.warning(str(e))

    @staticmethod
    def normalize_uri(uri):  # FIXME: Move to appkit.utils
        if uri is None:
            return None

        if '://' not in uri:
            uri = 'http://' + uri

        parsed = parse.urlparse(uri)
        if not parsed.path:
            parsed = parsed._replace(path='/')

        return parse.urlunparse(parsed)

    def origin_from_params(self, **params):
        p = params.copy()

        uri = self.normalize_uri(p.pop('uri', None))

        impl_name = p.pop('backend', None)
        if impl_name:
            impl_cls = self.app.get_implementation(Origin, impl_name)
        else:
            if not uri:
                msg = "Neither backend or uri was provided"
                raise TypeError(msg)

            impl_cls = self.origin_class_from_uri(uri)

            if impl_cls is None:
                msg = "No Origin plugin is compatible with '{uri}'"
                msg = msg.format(uri=uri)
                raise ValueError(msg)

            impl_name = impl_cls.__name__

        return impl_cls(
            self.app,
            uri=uri,
            iterations=p.pop('iterations', 1),
            display_name=p.pop('display_name', None),
            overrides=p,
            logger=logging.get_logger(impl_name)
        )

    def get_configured_origins(self):
        """Returns a list of configured origins in a specification form.

        This list is composed by importer.OriginSpec objects which are
        data-only structures. To get some usable object you may want to use
        importer.Importer.get_origins method"""

        specs = self.app.settings.get('origin', default={})
        if not specs:
            msg = "No origins defined"
            self.app.logger.warning(msg)
            return []

        ret = [
            self.origin_from_params(
                display_name=name,
                **params)
            for (name, params) in specs.items()
        ]
        ret = [x for x in ret if x is not None]
        return ret

    def process(self, *origins):
        data = []

        @asyncio.coroutine
        def get_contents_for_origin(origin):
            origin_data = yield from origin.get_data()
            data.extend(origin_data)

        tasks = [get_contents_for_origin(o) for o in origins]
        loop = asyncio.get_event_loop()
        loop.run_until_complete(asyncio.gather(*tasks))

        if not data:
            return []

        return self.process_source_data(*data)

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

        origin = self.app.get_extension(
            Origin,
            source.provider,
            uri=source.uri)

        loop = asyncio.get_event_loop()
        psources_data = loop.run_until_complete(origin.get_data())
        if not psources_data:
            return

        psources_data = self._process_remove_duplicates(psources_data)
        contexts = self._process_create_contexts(psources_data)
        self._process_insert_existing_sources(contexts)

        # Insert original source into context
        for ctx in contexts:
            if ctx.data['name'] == source.name:
                ctx.source = source
                continue

        self._process_update_existing_sources(contexts)
        self._process_insert_new_sources(contexts)
        ret = self._process_finalize(contexts)

        if not source.urn:
            raise exc.SourceResolveError(source)

    def run(self):
        return self.process(*self.get_configured_origins())

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

            meta = psrc.pop('meta')
            ret.append(ProcessingState(
                data=psrc,
                discriminator=discriminator,
                meta=meta,
                source=None,
                tags=[]
            ))

        return ret

    def _process_insert_existing_sources(self, contexts):
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


class ImporterCronTask(cron.CronTask):
    NAME = 'importer'
    INTERVAL = '3H'

    def run(self):
        self.app.importer.run()
        super().run()


class ProcessingState:
    def __init__(self, data=None, discriminator=None, meta=None, source=None,
                 tags=None):
        self.data = data or {}
        self.discriminator = discriminator
        self.meta = meta or {}
        self.source = source
        self.tags = tags or []


class ProcessingTag(enum.Enum):
    ADDED = 1
    UPDATED = 2
    NAME_UPDATED = 3


class Origin(extension.Extension):
    PROVIDER = None
    DEFAULT_URI = None
    URI_PATTERNS = None

    def __init__(self, *args, logger=None, display_name=None, uri=None,
                 iterations=1, overrides={}, **kwargs):

        uri = uri or self.DEFAULT_URI

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

        # Check overrides
        self._display_name = display_name
        self._uri = uri or self.default_uri
        self._iterations = iterations
        self._overrides = overrides.copy()

        super().__init__(*args, **kwargs)
        self.logger = logger or self.app.logger

    @classmethod
    def compatible_uri(cls, uri):
        attr_name = 'URI_PATTERNS'
        attr = getattr(cls, attr_name, None)

        if not (isinstance(attr, (list, tuple)) and len(attr)):
            msg = "Class {cls} must override {attr} attribute"
            msg = msg.format(cls=cls.__name__, attr=attr_name)
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

    @property
    def default_uri(self):
        if self.DEFAULT_URI is None:
            msg = "Class {clsname} must override DEFAULT_URI attribute"
            msg = msg.format(clsname=self.__class__.__name__)
            raise NotImplementedError(msg)

        return self.DEFAULT_URI

    @property
    def provider(self):
        if self.PROVIDER is None:
            msg = "Class {clsname} must override PROVIDER attribute"
            msg = msg.format(clsname=self.__class__.__name__)
            raise NotImplementedError(msg)

        return self.PROVIDER

    @property
    def display_name(self):
        return self._display_name

    @property
    def uri(self):
        return self._uri

    @property
    def iterations(self):
        return self._iterations

    @property
    def overrides(self):
        return self._overrides

    @asyncio.coroutine
    def get_data(self):
        ret = []

        @asyncio.coroutine
        def get_data_for_uri(uri):
            data = yield from self.process(uri)

            # self.process handles all exceptions from the fetch+parse process
            # In self.process we had to choose between:
            # - re-raise those exceptions
            # - raise a new exception from those exceptions
            # - simply return None
            # We keep this assert as a guard for this decision
            assert data is None or isinstance(data, list)

            if data:
                ret.extend(data)

        tasks = [get_data_for_uri(uri) for uri in self.get_uris()]
        yield from asyncio.gather(*tasks)

        return ret

    @asyncio.coroutine
    def process(self, uri):
        """
        Coroutine that fetches and parses an URI
        """

        # Fetch URI
        try:
            buff = yield from self.fetch(uri)

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
            return

        except Exception as e:
            msg = "Unhandled exception {type}: {e}"
            msg = msg.format(type=type(e), e=e)
            self.logger.critical(msg)
            raise

        if buff is None:
            msg = "Empty buffer for «{uri}»"
            msg = msg.format(uri=uri)
            self.logger.error(msg)
            return

        # Parse buffer
        try:
            psrcs = self.parse(
                buff,
                parser=self.app.settings.get('importer.parser'))

        except arroyo.exc.OriginParseError as e:
            msg = "Error parsing «{uri}»: {e}"
            msg = msg.format(uri=uri, e=e)
            self.logger.error(msg)
            return

        if psrcs is None:
            msg = ("Incorrect API usage in {name}, return None is not "
                   "allowed. Raise an Exception or return [] if no "
                   "sources are found")
            msg = msg.format(name=self.name)
            self.logger.critical(msg)
            return

        if not isinstance(psrcs, list):
            msg = "Invalid data type for URI «{uri}»: '{type}'"
            msg = msg.format(uri=uri, type=data.__class__.__name__)
            self.logger.critical(msg)
            return

        if len(psrcs) == 0:
            msg = "No sources found in «{uri}»"
            msg = msg.format(uri=uri)
            self.logger.warning(msg)
            return

        psrcs = self._normalize_source_data(*psrcs)

        msg = "Found {n_srcs_data} sources in {uri}"
        msg = msg.format(n_srcs_data=len(psrcs), uri=uri)
        self.logger.info(msg)

        return psrcs

    def get_uris(self):
        g = self.paginate()
        iters = max(1, self._iterations)

        yield from (next(g) for x in range(iters))

    @abc.abstractmethod
    def paginate(self):
        yield self._uri

    @staticmethod
    def paginate_by_query_param(url, key, default=1):
        """
        Utility generator for easy pagination
        """
        def alter_param(k, v):
            if k == key:
                try:
                    v = int(v) + 1
                except ValueError:
                    v = default

                v = str(v)

            return k, v

        yield url

        parsed = parse.urlparse(url)
        qsl = parse.parse_qsl(parsed.query)
        if key not in [x[0] for x in qsl]:
            qsl = qsl + [(key, default)]

        while True:
            qsl = [alter_param(*x) for x in qsl]
            yield parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path,
                                    parsed.params,
                                    parse.urlencode(qsl, doseq=True),
                                    parsed.fragment))

    @asyncio.coroutine
    def fetch(self, url):
        return (yield from self.app.fetcher.fetch(url))

    @abc.abstractmethod
    def parse(self, buff):
        return []

    @abc.abstractmethod
    def get_query_uri(self, query):
        return None

    def _normalize_source_data(self, *psrcs):
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
                msg = msg.format(name=self.provider,
                                 datatype=str(type(psrc)))
                self.logger.error(msg)
                continue

            # Insert provider name
            psrc['provider'] = self.provider

            # Apply overrides
            psrc.update(self._overrides)

            # Check required keys
            missing_keys = required_keys - set(psrc.keys())
            if missing_keys:
                msg = ("Origin «{name}» doesn't provide the required "
                       "following keys: {missing_keys}")
                msg = msg.format(name=self.provider,
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
                            name=self.provider, key=k,
                            expectedtype=kt, currtype=str(type(psrc[k])))
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
