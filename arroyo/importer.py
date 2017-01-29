# -*- coding: utf-8 -*-

import abc
import aiohttp
import asyncio
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

    def origin_from_params(self, **params):
        p = params.copy()
        provider = p.pop('provider', None)
        uri = p.pop('uri', None)
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
            msg = "No provider plugin is compatible with '{uri}'"
            msg = msg.format(uri=uri)
            raise ValueError(msg)

        return Origin(provider=extension, uri=uri, **p)

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

        tasks = [self.get_buffer_from_uri(origin, next(g))
                 for dummy in range(iterations)]

        ret = yield from asyncio.gather(*tasks)
        return ret

    def process(self, *origins):
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

    def process_source_data(self, *srcs_data):
        srcs = self.get_sources_for_data(*srcs_data)

        rev_srcs = {
            'added-sources': [],
            'updated-sources': [],
            'mediainfo-process-needed': [],
        }

        # Reverse source data structure
        for (src, flags) in srcs:
            if 'created' in flags:
                self.app.db.session.add(src)
                rev_srcs['added-sources'].append(src)

            if 'updated' in flags:
                rev_srcs['updated-sources'].append(src)

            if 'mediainfo-process-needed' in flags:
                rev_srcs['mediainfo-process-needed'].append(src)

        if rev_srcs['mediainfo-process-needed']:
            self.app.mediainfo.process(*rev_srcs['mediainfo-process-needed'])

        self.app.db.session.commit()

        # Launch signals
        self.app.signals.send('sources-added-batch',
                              sources=rev_srcs['added-sources'])

        self.app.signals.send('sources-updated-batch',
                              sources=rev_srcs['updated-sources'])

        # Save data
        self.app.db.session.commit()

        self.app.logger.info('{n} sources created'.format(
            n=len(rev_srcs['added-sources'])
        ))
        self.app.logger.info('{n} sources updated'.format(
            n=len(rev_srcs['updated-sources'])
        ))
        self.app.logger.info('{n} sources parsed'.format(
            n=len(rev_srcs['mediainfo-process-needed'])
        ))

        return srcs

    def get_sources_for_data(self, *psrcs):
        # First thing to do is organize input data
        psrcs = self.organize_data_by_most_recent(*psrcs)

        # Check for existings sources
        # Check psrcs to prevent SQLAlchemy error for using .in_ with an empty
        # list.
        existing_srcs = []
        if psrcs:
            keys = list(psrcs.keys())
            existing_srcs = self.app.db.session.query(models.Source).filter(
                models.Source._discriminator.in_(keys)
            ).all()

        # Name change is special
        name_updated_srcs = []

        for src in existing_srcs:
            src_data = psrcs[src._discriminator]

            if src.name != src_data['name']:
                name_updated_srcs.append(src)

            # Override srcs's properties with src_data properties
            for key in src_data:
                if key == '_discriminator':
                    continue

                # …except for 'created'
                # Some origins report created timestamps from heuristics,
                # variable or fuzzy data that is degraded over time.
                # For these reason we keep the first 'created' data as the most
                # fiable
                if key == 'created' and \
                   src.created is not None and \
                   src.created < src_data['created']:
                    continue

                setattr(src, key, src_data[key])

        # Check for missing sources
        missing_discriminators = (
            set(psrcs) -
            set([x._discriminator for x in existing_srcs])
        )

        # Create new sources
        created_srcs = [
            models.Source.from_data(**psrcs[x])
            for x in missing_discriminators
        ]

        # Create return data
        ret = {x: [] for x in itertools.chain(existing_srcs, created_srcs)}

        for x in created_srcs:
            ret[x].append('created')

        for x in existing_srcs:
            ret[x].append('updated')

        for x in created_srcs + name_updated_srcs:
            ret[x].append('mediainfo-process-needed')

        return list(ret.items())

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
        psrcs = loop.run_until_complete(origin.get_data())
        psrcs = self.organize_data_by_most_recent(*psrcs)

        for (disc, psrc) in psrcs.items():
            if source.name != psrc['name']:
                continue

            _update_source(psrc)

        if not source.urn:
            raise arroyo.exc.SourceResolveError(source)

        del(psrcs[source.urn])
        if psrcs:
            self.process_source_data(*psrcs.values())

    @staticmethod
    def organize_data_by_most_recent(*src_data):
        """
        Organizes the input list of source data into a dict.
        Keys will be the urn or permalink of the 'proto-sources'.
        In case of duplicates the oldest is discarted
        """
        ret = dict()

        for psrc in src_data:
            key = psrc['_discriminator']
            assert key is not None

            # Keep the most recent if case of duplicated
            if key not in ret or psrc['created'] > ret[key]['created']:
                ret[key] = psrc

        return ret

    def run(self):
        return self.process(*self.get_configured_origins())


class ImporterCronTask(kit.Task):
    __extension_name__ = 'importer'
    interval = '3H'

    def execute(self):
        self.app.importer.run()
