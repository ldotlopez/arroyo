# -*- coding: utf-8 -*-

import abc
import aiohttp
import asyncio
import itertools
import re
import traceback
from urllib import parse


from ldotcommons import (
    fetchers,
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

            # process got and exception and handled it, move on
            if data is None:
                return

            # check returned data
            if not isinstance(data, list):
                msg = "Invalid data type for URI «{uri}»: '{type}'"
                msg = msg.format(uri=uri, type=data.__class__.__name__)
                self.logger.error(msg)
                return

            ret.extend(data)

        tasks = [get_data_for_uri(uri) for uri in self.get_uris()]
        yield from asyncio.gather(*tasks)

        return ret

    @asyncio.coroutine
    def process(self, url):
        """
        Coroutine that fetches and parses an URL
        """
        try:
            buff = yield from self.fetch(url)
            if not buff:
                return None

        except Exception as e:
            msg = "Unhandled exception {type}: {e}"
            msg = msg.format(type=type(e), e=e)
            self.logger.critical(msg)
            raise

        psrcs = self.parse(buff)
        psrcs = self._normalize_source_data(*psrcs)

        msg = "Found {n_srcs_data} sources in {url}"
        msg = msg.format(n_srcs_data=len(psrcs), url=url)
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
    def fetch(self, url, params={}):
        try:
            return (yield from self.app.fetcher.fetch(url, **params))

        except (
            asyncio.CancelledError,
            asyncio.TimeoutError,
            aiohttp.errors.ClientOSError,
            ValueError  # url=foo (just 'foo')
        ) as e:
            msg = "{type} fetching «{url}»: {msg}"
            msg = msg.format(
                url=url, type=e.__class__.__name__, msg=str(e) or 'no reason'
            )
            self.logger.error(msg)

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

        return self.process_source_data(*data)

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
            raise exc.SourceResolveError(source)

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
        tmp = dict()

        for sd in src_data:
            k = sd['_discriminator']
            assert k is not None

            # If we got a duplicated urn keep the most recent
            if k in tmp and (sd['created'] < tmp[k]['created']):
                continue

            tmp[k] = sd

        return tmp

    def run(self):
        return self.process(*self.get_configured_origins())


class ImporterCronTask(cron.CronTask):
    NAME = 'importer'
    INTERVAL = '3H'

    def run(self):
        self.app.importer.run()
        super().run()
