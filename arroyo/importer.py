# -*- coding: utf-8 -*-

# Copyright (C) 2015 Luis López <luis@cuarentaydos.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301,
# USA.


import abc
import aiohttp
import asyncio
import enum
import re
import sys
import traceback
from urllib import parse


import bs4
from appkit import (
    loggertools,
    uritools,
    utils
)


import arroyo.exc
from arroyo import (
    bittorrentlib,
    kit,
    models
)


class Provider(kit.Extension):
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

    def __init__(self, app, *args, **kwargs):
        super().__init__(app, *args, **kwargs)
        self.settings = app.settings

    @abc.abstractmethod
    def paginate(self, uri):
        yield uri

    @abc.abstractmethod
    def get_query_uri(self, query):
        return None

    @abc.abstractmethod
    def fetch(self, fetcher, uri):
        return (yield from fetcher.fetch(uri))

    def parse_buffer(self, buffer):
        parser = self.settings.get('importer.parser')
        return bs4.BeautifulSoup(buffer, parser)

    @abc.abstractmethod
    def parse(self, buffer):
        msg = "Provider {name} doesn't implement parse method"
        msg = msg.format(name=self.__extension_name__)
        raise NotImplementedError(msg)

    def __unicode__(self):
        return "Provider({name})".format(
            name=self.__extension_name__)

    __str__ = __unicode__


class Origin:
    def __init__(self, provider, uri=None, iterations=1,
                 overrides={}):

        if not isinstance(provider, Provider):
            msg = "Invalid provider: {provider}"
            msg = msg.format(repr(provider))
            raise TypeError(msg)

        uri = uri or provider.DEFAULT_URI

        # Check strs
        strs = [
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
        self.uri = uritools.normalize(uri)
        self.iterations = iterations
        self.overrides = overrides.copy()
        self.logger = loggertools.getLogger(
            '{}-origin'.format(provider.__extension_name__))

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
    def __init__(self, app):
        self.app = app
        self.logger = loggertools.getLogger('importer')

        app.signals.register('source-added')
        app.signals.register('source-updated')
        app.signals.register('sources-added-batch')
        app.signals.register('sources-updated-batch')
        app.register_extension_point(Provider)
        app.register_extension_class(ImporterCronTask)

    def _settings_validator(self, key, value):
        """Validates settings"""
        return value

    def origin_from_params(self, provider=None, uri=None, iterations=1,
                           language=None, type=None):
        extension = None

        if not provider and not uri:
            msg = "Neither provider or uri was provided"
            raise TypeError(msg)

        if provider:
            # Get extension from provider
            extension = self.app.get_extension(Provider, provider)
            uri = uri or extension.DEFAULT_URI

            # Neither uri or extension.DEFAULT_URI is available
            if uri is None:
                msg = "Provider {name} needs and URI"
                msg = msg.format(name=extension.__extension_name__)
                raise exc.ArgumentError(msg)

            uri = uritools.normalize(uri)

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
                    self.logger.debug(msg)
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

        return Origin(provider=extension, uri=uri, iterations=iterations,
                      overrides=overrides)

    def origins_from_config(self):
        specs = self.app.settings.get('origin', default={})
        specs = [(name, params) for (name, params) in specs.items()]

        if not specs:
            msg = "No origins defined"
            self.logger.warning(msg)
            return []

        return [
            (name, self.origin_from_params(**params))
            for (name, params) in specs
        ]

    @asyncio.coroutine
    def get_buffer_from_uri(self, origin, uri):
        """ Get buffer (read) from URI using origin.

        In the 99% of the cases this means fetch some data from network

        Return:
          A tuple (origin, uri, result) where:
          - origin is the original origin argument
          - uri is the original uri argument
          - result is a bytes object with the content from uri or an Exception
            if something goes wrong
        """
        try:
            result = yield from origin.provider.fetch(self.app.fetcher, uri)

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
            result = e

        except Exception as e:
            print(traceback.format_exc(), file=sys.stderr)
            msg = "Unhandled exception {type}: {e}"
            msg = msg.format(type=type(e), e=e)
            self.logger.critical(msg)
            result = e

        if (not isinstance(result, Exception) and
                (result is None or result == '')):
            msg = "Empty or None buffer for «{uri}»"
            msg = msg.format(uri=uri)
            self.logger.error(msg)

        return (origin, uri, result)

    @asyncio.coroutine
    def get_buffers_from_origin(self, origin):
        """ Get all buffers from origin.

        An Origin can have several 'pages' or iterations.
        This methods is responsable to generate all URIs needed from origin
        and Importer.get_buffer_from_uri from each of them.

        Arguments:
          origin - The origin to process.
        Return:
          A list of tuples for each URI, see Importer.get_buffer_from_uri for
          information about those tuples.
        """
        g = origin.provider.paginate(origin.uri)
        iterations = max(1, origin.iterations)

        # Generator can raise StopIteration before iterations is reached.
        # We use a for loop instead of a comprehension expression to catch
        # gracefully this situation.
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

        data = []
        for (origin, uri, res) in results:
            if isinstance(res, Exception) or res is None or res == '':
                continue

            try:
                res = origin.provider.parse(res)

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

            res = self._normalize_source_data(origin, *res)
            data.extend(res)

            msg = "{n} sources found at {uri}"
            msg = msg.format(n=len(res), uri=uri)
            self.logger.info(msg)

        return data

    def process(self, *origins):
        data = self.get_data_from_origin(*origins)
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

        origin = self.origin_from_params(provider=source.provider,
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
        origins = self.origins_from_config()
        if not origins:
            msg = "No origins defined"
            self.logger.warning(msg)
            return []

        origins = (origin for (dummy, origin) in origins)
        return self.process(*origins)

    def _normalize_source_data(self, origin, *psrcs):
        """ Normalize input data for given origin.

        Args:
          origin - An Origin object. All psrcs should be the result of this
                   origin.
          psrcs - List of psources (raw dicts) to be normalized.

        Returns:
          A list of normalized psources (dicts).
        """

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
                normalized_urn = bittorrentlib.normalize_urn(urn)

                # FIXME: This is a hack, fix uritools.alter_query_params
                psrc['uri'] = psrc['uri'].replace(
                    'xt=' + urn, 'xt=' + normalized_urn)
                psrc['urn'] = normalized_urn

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

    def _process_remove_duplicates(self, psources):
        """ Remove duplicated sources.

        Filter psource list to exclude duplicates.
        The duplicated with the newest stamp (the 'created' key) is keeped.

        Args:
          psource - List of dicts representing proto-sources.
        Returns:
          A list of dicts without duplicates.
        """
        ret = dict()

        for psrc in psources:
            key = psrc['_discriminator']
            assert key is not None

            # Keep the most recent if case of duplicated
            if key not in ret or psrc['created'] > ret[key]['created']:
                ret[key] = psrc

        return list(ret.values())

    def _process_create_contexts(self, psources):
        """ Initialize contexts for the subsequent process.

        A new context is created for each psource.

        Args:
          psources - List of data (or pseudo-sources).
        """
        now = utils.now_timestamp()

        ret = []
        for psrc in psources:
            discriminator = psrc.pop('_discriminator')
            assert discriminator is not None

            meta = psrc.pop('meta', {})
            psrc['created'] = psrc.get('created') or now
            psrc['last_seen'] = psrc.get('last_seen') or now
            ret.append(_ProcessingContext(
                data=psrc,
                discriminator=discriminator,
                meta=meta,
                source=None,
                tags=[]
            ))

        return ret

    def _process_insert_existing_sources(self, contexts):
        """ Search for existings sources.

        Exisisting sources are added to contexts based on the  discriminators.

        Args:
          contexts - List of contexts
        """

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
        """ Update existing sources with data from context.

        Update sources from matching data.
        Those sources are updated and relevant tags added.

        Args:
          contexts - List of contexts.
        """
        for ctx in contexts:
            updated = False

            if ctx.source is None:
                continue

            if ctx.source.name != ctx.data['name']:
                updated = True
                ctx.tags.append(_ProcessingTag.NAME_UPDATED)

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

                old_value = getattr(ctx.source, key, None)
                new_value = ctx.data.get(key, None)
                if new_value and new_value != old_value:
                    updated = True
                    setattr(ctx.source, key, new_value)

            if updated:
                ctx.tags.append(_ProcessingTag.UPDATED)

    def _process_insert_new_sources(self, contexts):
        """ Create new source from contexts if necessary.

        Creates new sources for each context with source.
        _ProcessingTag.ADDED is added for each of them.

        Args:
          contexts - List of contexts
        """
        for ctx in contexts:
            if ctx.source is not None:
                continue

            ctx.source = models.Source(**ctx.data)
            ctx.tags.append(_ProcessingTag.ADDED)

    def _process_finalize(self, contexts):
        """ Final stage of processing.

        - Sources are processed in the mediainfo engine based on tags from
          contexts.
        - 'sources-added-batch' and 'sources-updated-batch' signals are send
        - Some statistics are printed.

        Args:
          contexts - List of sources from contexts.
        """
        added = []
        updated = []
        name_updated = []

        for ctx in contexts:
            if _ProcessingTag.ADDED in ctx.tags:
                added.append(ctx)

            if _ProcessingTag.NAME_UPDATED in ctx.tags:
                name_updated.append(ctx)

            if _ProcessingTag.UPDATED in ctx.tags:
                updated.append(ctx)

        self.app.db.session.add_all([ctx.source for ctx in added])

        sources_and_metas = [
            (ctx.source, ctx.meta)
            for ctx in set(added + name_updated)
        ]

        if sources_and_metas:
            self.app.mediainfo.process(*sources_and_metas)

        # It's important to call commit here, Mediainfo.process doesn't do a
        # commit
        self.app.db.session.commit()

        self.app.signals.send(
            'sources-added-batch',
            sources=[ctx.source for ctx in added])
        self.app.signals.send(
            'sources-updated-batch',
            sources=[ctx.source for ctx in name_updated + updated])

        msg = '{n} sources {action}'
        stats = [
            ('added', added),
            ('updated', updated),
            ('parsed', sources_and_metas)
        ]
        for (action, group) in stats:
            msg_ = msg.format(n=len(group), action=action)
            self.logger.info(msg_)

        ret = [ctx.source for ctx in contexts]
        return ret


class _ProcessingContext:
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

        base = ("<arroyo.importer._ProcessingContext({internals}) object at "
                " {id}>")
        return base.format(internals=internals, id=hex(id(self)))


class _ProcessingTag(enum.Enum):
    ADDED = 1
    UPDATED = 2
    NAME_UPDATED = 3


class ImporterCronTask(kit.Task):
    __extension_name__ = 'importer'
    INTERVAL = '3H'

    def execute(self, app):
        app.importer.run()
