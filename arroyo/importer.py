# -*- coding: utf-8 -*-

import asyncio
from itertools import chain
from urllib import parse

import aiohttp
from ldotcommons import fetchers, store, utils

from arroyo import asyncscheduler
from arroyo import downloads, cron, extension, models


class IncompatibleQueryError(Exception):
    pass


class Importer:
    """
    API for import.
    """

    def __init__(self, app):
        self.app = app
        self.app.settings.add_validator(self._settings_validator)

        self._sched = None
        self._logger = app.logger.getChild('importer')

        app.signals.register('source-added')
        app.signals.register('source-updated')
        app.signals.register('sources-added-batch')
        app.signals.register('sources-updated-batch')

        app.register_extension('import', ImporterCronTask)

    def _settings_validator(self, k, v):
        # Supported keys are:
        #
        # origin.*.backend (str)
        # origin.*.url (str, NoneType)
        # origin.*.iterations (int, NoneType =>1)
        # origin.*.type (str, NoneType)
        # origin.*.language (str, NoneType)

        parts = k.split('.', 2)
        if parts[0] != 'origin' or len(parts) != 3:
            return v

        rootns, name, prop = parts

        if prop not in ('backend', 'url', 'iterations', 'type', 'language'):
            raise store.ValidationError(k, v, 'Invalid option')

        if prop == 'backend':
            if v is None or not isinstance(v, str) or v == '':
                msg = 'Must be a non-empty string'
                raise store.ValidationError(k, v, msg)

        if prop in ['url', 'language', 'type']:
            if not isinstance(v, (utils.NoneType, str)) or v == '':
                msg = 'Must be empty or a str'
                raise store.ValidationError(k, v, msg)

        if prop == 'iterations':
            if v is None:
                v = 1

            elif not isinstance(v, int):
                msg = 'Must be an integer'
                raise store.ValidationError(k, v, msg)

        return v

    def get_origins(self):
        """Returns a list of configured origins.

        This list is composed by plugin.Origin objects.
        """

        return list(map(
            self.get_origin_for_origin_spec,
            self.get_origins_specs()))

    def get_origins_specs(self):
        """Returns a list of configured origins in a specification form.

        This list is composed by importer.OriginSpec objects which are
        data-only structures. To get some usable object you may want to use
        importer.Importer.get_origins method
        """

        defs = self.app.settings.get('origin', default={})
        if not defs:
            msg = "No origins defined"
            self.app.logger.warning(msg)
            return []

        ret = []
        for (name, params) in defs.items():
            try:
                spec = OriginSpec(name, **params)
                ret.append(spec)
            except TypeError:
                msg = "Invalid origin {name}"
                msg = msg.format(name=name)
                self.app.logger.warn(msg)

        return ret

    def get_origins_for_query_spec(self, query_spec):
        """Get autogenerated origins for a selector.QuerySpec object.

        One query can produce zero or more or plugin.Origins from the activated
        origin extensions.

        Returned origins are configured with one iteration.
        """

        msg = "Discovering origins for {query}"
        msg = msg.format(query=query_spec)
        self.app.logger.info(msg)

        impls = self.app.get_implementations(Origin)
        if not impls:
            msg = ("There are no origin implementations available or none of "
                   "them is enabled, check your configuration")
            self.app.logger.warning(msg)
            return []

        ret = []
        for (name, impl) in impls.items():
            try:
                origin = impl(self.app, query_spec=query_spec)
                ret.append(origin)
                msg = " Found compatible origin '{name}'"
                msg = msg.format(name=name)
                self.app.logger.info(msg)
            except IncompatibleQueryError:
                pass

        if not ret:
            msg = "No compatible origins found for {query}"
            msg = msg.format(query=query_spec)
            self.app.logger.warning(msg)

        return ret

    def get_origin_for_origin_spec(self, origin_spec):
        backend = origin_spec.get('backend')
        return self.app.get_extension(
            Origin, backend,
            origin_spec=origin_spec)

    def process(self, *origins):
        """Core function for importer.Importer.

        1. Iterate over the URLs produced by origin
        2. Fetch URL and parse content
        3. Process content thru origin parser to get models.Source object
        4. Insert or update DB with those models.

        Within this process the 'created' and 'last_seen' fields from
        models.Source are set.

        Some signals are emited:

        - 'source-added'
        - 'source-updated'
        - 'sources-added-batch',
        - 'sources-updated-batch',
        """

        # Get, sched and run all tasks from origins
        self._sched = ImporterRunner(
            maxtasks=self.app.settings.get('async-max-concurrency'),
            timeout=self.app.settings.get('async-timeout'),
            logger=self.app.logger.getChild('asyncsched'))

        for origin in origins:
            self._sched.sched(*origin.get_tasks())

        self._sched.run()

        # Remove duplicates
        tmp = dict()
        for src_data in self._sched.results:
            k = src_data['urn']

            if k in tmp and (src_data['created'] < tmp[k]['created']):
                continue

            tmp[k] = src_data

        self._sched = None
        results = tmp

        # Check which sources are created and which ones are updated from data
        #
        urns = list(results.keys())

        # Handle existing sources updating properties
        q = self.app.db.session.query(models.Source)
        if urns:
            q = q.filter(models.Source.urn.in_(urns))
            existing_srcs = q.all()
        else:
            existing_srcs = []

        for src in existing_srcs:
            src_data = results[src.urn]

            # Override srcs's properties with src_data properties
            for key in src_data:
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

        # Handle newly created sources
        missing_urns = set(urns) - set((x.urn for x in existing_srcs))
        created_srcs = [models.Source.from_data(**results[urn])
                        for urn in missing_urns]

        all_srcs = chain(
            ((x, False) for x in existing_srcs),
            ((x, True) for x in created_srcs)
        )

        now = utils.now_timestamp()
        ret = {
            'added-sources': [],
            'updated-sources': [],
        }

        for src, created in all_srcs:
            src.last_seen = now

            if created:
                self.app.db.session.add(src)
                signal_name = 'source-added'
                batch_key = 'added-sources'
            else:
                signal_name = 'source-updated'
                batch_key = 'updated-sources'

            self.app.signals.send(signal_name, source=src)

            ret[batch_key].append(src)

        self.app.signals.send('sources-added-batch',
                              sources=ret['added-sources'])
        self.app.signals.send('sources-updated-batch',
                              sources=ret['updated-sources'])

        self.app.db.session.commit()

        self.app.logger.info('{n} sources created'.format(
            n=len(ret['added-sources'])
        ))
        self.app.logger.info('{n} sources updated'.format(
            n=len(ret['updated-sources'])
        ))

        return ret

    def process_spec(self, origin_spec):
        return self.process(
            self.get_origin_for_origin_spec(origin_spec)
        )

    def process_query(self, query_spec):
        return self.process(
            *self.get_origins_for_query_spec(query_spec)
        )

    def push_to_sched(self, *coros):
        if not self._sched:
            msg = "Scheduler not available at this phase"
            self.app.error(msg)
            return

        self._sched.sched(*coros)

    def run(self):
        return self.process(*self.get_origins())


class ImporterRunner(asyncscheduler.AsyncScheduler):
    def result_handler(self, result):
        self.results.extend(result)

    def exception_handler(self, loop, ctx):
        msg = 'Exception raised: {msg}'
        msg = msg.format(msg=ctx['message'])

        e = ctx.get('exception')
        if e:
            msg += ' {exctype}: {excstr}'
            msg = msg.format(exctype=type(e), excstr=e)

        self._logger.error(msg)

        self.feed()


class OriginSpec(utils.InmutableDict):
    """Support class to store specification of an origin.

    This class only stores information of an origin, it is not the origin.

    Instances of importer.OriginSpec are used to get a configured plugin.Origin
    from importer.Importer
    """
    def __init__(self, name, backend, url=None, iterations=1, type=None,
                 language=None):
        # Check strs
        strs = [('name', name, False),
                ('backend', backend, False),
                ('url', url, True),
                ('type', type, True),
                ('language', language, True)]

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

        super().__init__(name=name, backend=backend, url=url,
                         iterations=iterations, type=type, language=language)

    def __repr__(self):
        return "<{pkg}.{clsname}: '{name}'>".format(
            pkg=__name__,
            clsname=self.__class__.__name__,
            name=self.get('name', '(null)'))


class Origin(extension.Extension):
    """Extension point for implemented Origin extension.

    Origin extensions are responsible to parse websites or fetch information
    from other services.

    They must override or implement:

    - class attribute BASE_URL: Default URL (or URI) of website. This URL will
        be used if no other is specified
    - class attribute PROVIDER_NAME: Unique (among other ext.Origin
        implementations) identifier
    - method process_buffer: Given a utf8 buffer this function should return a
        list of dicts with found information. Those dicts can containing the
        same fields present in models.Source, only name and uri are mandatory

    They can override:

    - method paginate: Given a URL returns a generator object which yields that
        URL and subsequent URLs
    - method get_query_url: Given a selector.QuerySpec object returns the URL
        containing that search result for the website that ext.Origin
        implements

    This class also contains some helper methods for child classes, check docs
    or code for more information.
    """

    def __init__(self, app, origin_spec=None, query_spec=None):
        super(Origin, self).__init__(app)

        if origin_spec and query_spec:
            msg = 'origin_spec and query_spec are mutually exclusive'
            raise ValueError(msg)

        self.logger = app.logger.getChild(self.PROVIDER_NAME)

        self._iteration = 0

        if origin_spec:
            self._name = origin_spec['name']
            self._url = origin_spec['url'] or self.BASE_URL
            self._iterations = origin_spec['iterations']
            self._overrides = {k: v for (k, v) in {
                'type': origin_spec['type'],
                'language': origin_spec['language'],
            }.items() if v is not None}

        elif query_spec:
            self._name = 'internal query'
            self._url = self.get_query_url(query_spec)

            if not self._url:
                raise IncompatibleQueryError(query_spec)

            self._iterations = 1
            self._overrides = {}

        else:
            raise ValueError('None of origin_spec or query_spec is specified')

    @property
    def iterations(self):
        return self._iterations

    def urls(self):
        """
        Generator that provides URLs from origin
        """
        if not self._url:
            return

        iters = max(1, self._iterations)

        g = self.paginate(self._url)
        return (next(g) for x in range(iters))

    def paginate_by_query_param(self, url, key, default=1):
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

    def get_query_url(self, query):
        return

    def get_tasks(self):
        return [self.process(url) for url in self.urls()]

    @asyncio.coroutine
    def fetch(self, url):
        s = self.app.settings

        fetcher = fetchers.AIOHttpFetcher(**{
            k.replace('-', '_'): v
            for (k, v) in s.get('fetcher.options').items()
        })
        buff = yield from fetcher.fetch(url)

        return buff

    @asyncio.coroutine
    def process(self, url):
        """
        Coroutine that fetches and parses an URL
        """
        msg = "Fetching «{url}»"
        msg = msg.format(url=url)
        self.app.logger.info(msg)

        try:
            buff = yield from self.fetch(url)

        except asyncio.CancelledError as e:
            msg = "Fetch cancelled '{url}' (possibly timeout)"
            msg = msg.format(url=url)
            self.app.logger.error(msg)
            return []

        except aiohttp.errors.ClientOSError as e:
            msg = "Client error fetching {url}: {e}"
            msg = msg.format(url=url, e=e)
            self.app.logger.error(msg)
            return []

        except Exception as e:
            msg = "Unhandled exception {type}: {e}"
            msg = msg.format(type=type(e), e=e)
            self.app.logger.critical(msg)
            raise

        srcs_data = self.parse(buff)

        ret = self._normalize_source_data(srcs_data)
        if not isinstance(ret, list):
            ret = list(ret)

        msg = "Found {n_srcs_data} sources in {url}"
        msg = msg.format(n_srcs_data=len(ret), url=url)
        self.app.logger.info(msg)

        return ret

    def _normalize_source_data(self, data):
        now = utils.now_timestamp()

        def _normalize(psrc):
            if not isinstance(psrc, dict):
                msg = "Origin «{name}» emits invalid data type: {datatype}"
                msg = msg.format(name=self.PROVIDER_NAME,
                                 datatype=str(type(psrc)))
                self.app.logger.error(msg)
                return None

            # Insert provider name
            psrc['provider'] = self.PROVIDER_NAME

            # Apply overrides
            psrc.update(self._overrides)

            # Check required keys
            required_keys = set(['provider', 'uri', 'name'])
            missing_keys = required_keys - set(psrc.keys())
            if missing_keys:
                msg = ("Origin «{name}» doesn't provide the required "
                       "following keys: {missing_keys}")
                msg = msg.format(name=self.PROVIDER_NAME,
                                 missing_keys=missing_keys)
                self.app.logg.error(msg)
                return None

            # Only those keys are allowed
            allowed_keys = required_keys.union(set([
                'created', 'size', 'seeds', 'leechers', 'language', 'type'
            ]))

            forbiden_keys = [k for k in psrc if k not in allowed_keys]
            if forbiden_keys:
                msg = ("Origin «{name}» emits the following invalid "
                       "properties for its sources: {forbiden_keys}")
                msg = msg.format(name=psrc['provider'],
                                 forbiden_keys=forbiden_keys)
                self.app.logger.warning(msg)

            psrc = {k: psrc.get(k, None) for k in allowed_keys}

            # Check value types
            checks = [
                ('name', str),
                ('uri', str),
                ('created', int),
                ('size', int),
                ('seeds', int),
                ('leechers', int)
            ]
            for k, kt in checks:
                if (psrc[k] is not None) and (not isinstance(psrc[k], kt)):
                    try:
                        psrc[k] = kt(psrc[k])
                    except (TypeError, ValueError):
                        msg = ("Origin «{name}» emits invalid «{key}» value. "
                               "Expected {expectedtype} (or compatible), got "
                               "{currtype}")
                        msg = msg.format(
                            name=self.PROVIDER_NAME, key=k,
                            expectedtype=kt, currtype=str(type(psrc[k])))
                        self.app.logger.error(msg)
                        return None

            # Calculate URN.
            # IMPORTANT: URN is **lowercased** and **sha1-encoded**
            try:
                qs = parse.urlparse(psrc['uri']).query
                urn = parse.parse_qs(qs)['xt'][-1]
                urn = urn.lower()
                sha1urn, b64urn = downloads.calculate_urns(urn)
                psrc['urn'] = sha1urn
            except (IndexError, KeyError):
                return None

            # Fix created
            psrc['created'] = psrc.get('created', None) or now
            return psrc

        # Normalize data structure
        return filter(lambda x: x is not None, map(_normalize, data))

    def __repr__(self):
        return "<%s (%s)>" % (
            self.__class__.__name__,
            getattr(self, '_url', '(None)'))


class ImporterCronTask(cron.CronTask):
    NAME = 'importer'
    INTERVAL = '3H'

    def run(self):
        self.app.importer.run()
        super().run()
