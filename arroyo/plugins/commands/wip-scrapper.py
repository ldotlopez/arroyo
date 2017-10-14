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


import asyncio
import functools
import threading
import contextlib


from appkit import loggertools, uritools


from arroyo import pluginlib, models
from arroyo.importer import Provider, Origin


class Origin2(Origin):
    def __init__(self, uri, iterations=1,
                 overrides={}):

        # Check URI
        if not isinstance(uri, str) or uri == '':
            msg = "Invalid value '{value}' for '{name}'. It must be a str"
            msg = msg.format(name='uri', value=uri)
            raise TypeError(msg)

        # Check iterations
        if not isinstance(iterations, int):
            msg = "Invalid value '{value}' for '{name}'. It must be an int"
            msg = msg.format(name='iterations', value=iterations)
            raise TypeError(msg)

        # Check overrides
        overrides_ = {}
        msg = "override key '{key}' must be a non-empty string"
        for (key, value) in overrides.items():
            if key == 'language' or key == 'type':
                if value is None:
                    continue

                if not isinstance(value, str):
                    msg_ = msg.format(key=key)
                    raise TypeError(msg_)

                if value == '':
                    msg_ = msg.format(key=key)
                    raise ValueError(msg_)

                overrides_[key] = value

            else:
                msg = "Unknow override key: '{key}'"
                msg = msg.format(key=key)
                raise TypeError(msg)

        self.uri = uritools.normalize(uri)
        self.iterations = iterations
        self.overrides = overrides_

    def __unicode__(self):
        return 'Origin({uri})'.format(
            uri=self.uri)

    def __str__(self):
        return self.__unicode__()

    def __repr__(self):
        return '<arroyo.importer.Origin ({uri}) object at {hexid}>'.format(
            uri=self.uri,
            hexid=hex(id(self)))


class Scrapper:
    def __init__(self, app, logger=None, fetcher=None):
        self.app = app
        self.logger = logger or app.logger.getChild('scrapper')
        self.fetcher = fetcher or app.fetcher

    def origin_for_provider(self, provider):
        if not isinstance(provider, Provider):
            raise TypeError(provider)

        return Origin2(uri=provider.DEFAULT_URI)

    def provider_for_origin(self, origin):
        for (name, ext) in self.app.get_extensions_for(Provider):
            if ext.compatible_uri(origin.uri):
                extension = ext
                msg = "Found compatible provider for {uri}: {provider}"
                msg = msg.format(
                    uri=origin.uri,
                    provider=extension.__extension_name__)
                self.logger.debug(msg)
                return ext

        msg = "No compatible provider for {origin} found, fallback to generic"
        msg = msg.format(origin=origin)
        self.logger.info(msg)

        return self.app.get_extension(Provider, 'generic')

    @asyncio.coroutine
    def scrap_uri(self, uri, provider):
        def _build_src(src):
            tags = [
                models.SourceTag(
                    key=provider.__extension_name__ + '.' + k,
                    value=v
                ) for (k, v) in src.pop('meta', {}).items()
            ]
            return models.Source(
                provider=provider.__extension_name__,
                tags=tags,
                **src)

        sources = yield from (_scrap(
            uri,
            lambda x: provider.fetch(self.fetcher, x),
            provider.parse))

        return [_build_src(src) for src in sources]

    @asyncio.coroutine
    def scrap_multiple_uris(self, uris, provider):
        @asyncio.coroutine
        def _wrap(uri):
            sources = yield from self.scrap_uri(uri, provider)
            return (uri, sources)

        tasks = [_wrap(uri) for uri in uris]
        results = [src for src in
                   (yield from asyncio.gather(*tasks))
                   if src]

        return results

    @asyncio.coroutine
    def scrap(self, origin, provider):
        paginator = provider.paginate(origin.uri)

        # Generator can raise StopIteration before iterations is reached.
        # We use a for loop instead of a comprehension expression to catch
        # gracefully this situation.
        uris = []
        for i in range(origin.iterations):
            try:
                uris.append(next(paginator))
            except StopIteration:
                msg = ("'{provider}' has stopped the pagination after {index} "
                       "iteration(s)")
                msg = msg.format(provider=provider.__extension_name__, index=i)
                self.logger.warning(msg)
                break

        results = yield from self.scrap_multiple_uris(uris, provider)

        for (uri, sources) in results:
            msg = "Found {n} sources in {uri}"
            msg = msg.format(n=len(sources), uri=uri)
            print(msg)

        sources = functools.reduce(
            lambda acc, x: acc + x[1],
            results,
            [])

        return sources


class DBController:
    """
    https://stackoverflow.com/questions/270879/efficiently-updating-database-using-sqlalchemy-orm
    """

    def __init__(self, sess):
        self._sess = sess
    #     self._lock = threading.Semaphore(value=1)

    # @property
    # @contextlib.contextmanager
    # def sess(self):
    #     with self._lock:
    #         yield self._sess

    def create_source(self, data):
        raise NotImplementedError()

    def update_source(self, original, updated):
        updatable_attrs = [
            'created',
            'entity',
            'language',
            'last_seen',
            'leechers',
            'name',
            'provider',
            'seeds',
            'size',
            'tags',
            'type',
        ]

        if original.last_seen >= updated.last_seen:
            raise ValueError('updated source is older than original')

        for attr in updatable_attrs:
            # …except for 'created'
            # Some origins report created timestamps from heuristics,
            # variable or fuzzy data that is degraded over time.
            # For these reason we keep the first 'created' data as the
            # most fiable
            if (attr == 'created' and
                    original.created is not None and
                    original.created < updated.created):
                continue

            old_value = getattr(original, attr, None)
            new_value = getattr(updated, attr, None)

            if attr == 'tags':
                tags = new_value.all()
                for x in tags:
                    x.source = updated
                continue

            if old_value != new_value:
                setattr(original, attr, new_value)

        self._sess.commit()

    def store_source(self, source):
        return self.store_sources([source])[0]

    def store_sources(self, sources):
        # Remove duplicates in input data
        # Keep the most recent if case of duplicated
        new_sources = {}
        for src in sources:
            if (src._discriminator not in new_sources or
                    src.created > new_sources[src._discriminator].created):
                new_sources[src._discriminator] = src

        # Get existing sources into existing_sources map
        qs = self._sess.query(models.Source)
        qs = qs.filter(
            models.Source._discriminator.in_(new_sources.keys()))
        existing_sources = {src._discriminator: src for src in qs}

        # Update existing sources with new data
        for (discr, src) in existing_sources.items():
            self.update_source(src, new_sources[discr])
            del(new_sources[discr])

        self._sess.add_all(new_sources.values())
        self._sess.commit()

        return list(existing_sources.values()) + list(new_sources.values())


class ScrapperCommand(pluginlib.Command):
    __extension_name__ = 'scrapper'

    HELP = 'Scan sources (i.e. websites)'
    ARGUMENTS = (
        pluginlib.cliargument(
            '--provider',
            dest='provider',
            type=str,
            help='Provider to use'),
        pluginlib.cliargument(
            '-u', '--uri',
            dest='uri',
            type=str,
            default=None,
            help='Base URI to scan'),
        pluginlib.cliargument(
            '-i', '--iterations',
            dest='iterations',
            type=int,
            default=1,
            help=('Iterations to run over base URI (Think about pages in a '
                  'website)')),
        pluginlib.cliargument(
            '-t', '--type',
            dest='type',
            type=str,
            help='Override type of found sources'),
        pluginlib.cliargument(
            '-l', '--language',
            dest='language',
            type=str,
            help='Override language of found sources'),
        pluginlib.cliargument(
            '--from-config',
            dest='from_config',
            action='store_true',
            default=False,
            help='Import from the origins defined in the configuration file')
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = loggertools.getLogger('scan')

    def execute(self, app, arguments):
        scrapper = Scrapper(app)
        dbctrl = DBController(self.app.db.session)

        if arguments.from_config and arguments.provider:
            msg = ("Only one of --from-config or --provider options can be "
                   "specified. They are mutually exclusive.")
            raise pluginlib.exc.ArgumentsError(msg)

        provider = None
        origin = None

        if arguments.provider:
            provider = self.app.get_extension(Provider, arguments.provider)

        if arguments.uri:
            origin = Origin2(uri=arguments.uri)

        elif arguments.from_config:
            raise NotImplementedError()

        if not origin and not provider:
            msg = "Incorrect usage"
            raise pluginlib.exc.ArgumentsError(msg)

        if not origin:
            origin = scrapper.origin_for_provider(provider)

        if not provider:
            provider = scrapper.provider_for_origin(origin)

        origin.iterations = arguments.iterations
        origin.overrides = {
            'type': arguments.type,
            'language': arguments.language
        }

        sources = sync_coroutine(scrapper.scrap(origin, provider=provider))
        sources = dbctrl.store_sources(sources)
        print("saved {} sources".format(len(sources)))


@asyncio.coroutine
def _scrap(uri, fetch_fn, parse_fn):
    buff = yield from fetch_fn(uri)
    psrcs = parse_fn(buff)
    return psrcs


def sync_coroutine(fut, loop=None):
    if not loop:
        loop = asyncio.get_event_loop()
    return loop.run_until_complete(fut)


__arroyo_extensions__ = [
    ScrapperCommand
]
