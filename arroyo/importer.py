# -*- coding: utf-8 -*-

import abc
import aiohttp
import asyncio
import itertools
import traceback
from urllib import parse


from ldotcommons import (
    fetchers,
    logging,
    utils
)


from arroyo import (
    asyncscheduler,
    cron,
    downloads,
    exc,
    extension,
    models
)


class Origin(extension.Extension):
    PROVIDER = None
    DEFAULT_URI = None

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
    def get_sources_data(self, task_manager):
        self._task_manager = task_manager  # FIXME
        for url in self.get_uris():
            task_manager.sched(self.process(url))

        return []

    def add_process_task(self, url):
        self._task_manager.sched(self.process(url))

    @asyncio.coroutine
    def process(self, url):
        """
        Coroutine that fetches and parses an URL
        """
        msg = "Fetching «{url}»"
        msg = msg.format(url=url)
        self.logger.info(msg)

        try:
            buff = yield from self.fetch(url)

        except asyncio.CancelledError as e:
            msg = "Fetch cancelled '{url}' (possibly timeout)"
            msg = msg.format(url=url)
            self.logger.error(msg)
            return []

        except aiohttp.errors.ClientOSError as e:
            msg = "Client error fetching {url}: {e}"
            msg = msg.format(url=url, e=e)
            self.logger.error(msg)
            return []

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

    @asyncio.coroutine
    def fetch(self, url, params={}):

        """
        Coroutine that fetches and parses an URL
        """
        msg = "Fetching «{url}»"
        msg = msg.format(url=url)
        self.logger.info(msg)

        s = self.app.settings
        fetcher = fetchers.AIOHttpFetcher(
            logger=self.logger.getChild('fetcher'),
            **{
                k.replace('-', '_'): v
                for (k, v) in s.get('fetcher').items()
            })
        buff = yield from fetcher.fetch(url)

        return buff

    @abc.abstractmethod
    def parse(self, buffer):
        pass

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

    def get_configured_origins(self):
        """Returns a list of configured origins in a specification form.

        This list is composed by importer.OriginSpec objects which are
        data-only structures. To get some usable object you may want to use
        importer.Importer.get_origins method"""

        def _build_origin(**params):
            try:
                impl_name = params.pop('backend')
                return self.app.get_extension(
                    Origin, impl_name, logger=logging.get_logger(impl_name),
                    **params)

            except TypeError as e:
                msg = "Invalid origin {name}: {msg}"
                msg = msg.format(name=name, msg=str(e))
                self.app.logger.error(msg)
                return None

        specs = self.app.settings.get('origin', default={})
        if not specs:
            msg = "No origins defined"
            self.app.logger.warning(msg)
            return []

        ret = [
            _build_origin(
                display_name=name,
                **params)
            for (name, params) in specs.items()
        ]
        ret = [x for x in ret if x is not None]
        return ret

    def process(self, *origins):
        self._sched = ImporterRunner(
             maxtasks=self.app.settings.get('async-max-concurrency'),
             timeout=self.app.settings.get('async-timeout'),
             logger=self.app.logger.getChild('asyncsched'))

        # Weird but temporal
        srcs_data = self._sched.run(*[
            x.get_sources_data(self._sched) for x in origins
        ])

        # Disable task manager
        self._sched = None

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
            traceback.print_exc()

        self.feed()


class ImporterCronTask(cron.CronTask):
    NAME = 'importer'
    INTERVAL = '3H'

    def run(self):
        self.app.importer.run()
        super().run()


# class OldImporter:
#     """
#     API for import.
#     """

#     def __init__(self, app):
#         self.app = app
#         self.app.settings.add_validator(self._settings_validator)

#         self._sched = None
#         self._logger = app.logger.getChild('importer')

#         app.signals.register('source-added')
#         app.signals.register('source-updated')
#         app.signals.register('sources-added-batch')
#         app.signals.register('sources-updated-batch')

#         app.register_extension('import', ImporterCronTask)

#     def _settings_validator(self, k, v):
#         # Supported keys are:
#         #
#         # origin.*.backend (str)
#         # origin.*.url (str, NoneType)
#         # origin.*.iterations (int, NoneType =>1)
#         # origin.*.type (str, NoneType)
#         # origin.*.language (str, NoneType)

#         parts = k.split('.', 2)
#         if parts[0] != 'origin' or len(parts) != 3:
#             return v

#         rootns, name, prop = parts

#         if prop not in ('backend', 'url', 'iterations', 'type', 'language'):
#             raise store.ValidationError(k, v, 'Invalid option')

#         if prop == 'backend':
#             if v is None or not isinstance(v, str) or v == '':
#                 msg = 'Must be a non-empty string'
#                 raise store.ValidationError(k, v, msg)

#         if prop in ['url', 'language', 'type']:
#             if not isinstance(v, (utils.NoneType, str)) or v == '':
#                 msg = 'Must be empty or a str'
#                 raise store.ValidationError(k, v, msg)

#         if prop == 'iterations':
#             if v is None:
#                 v = 1

#             elif not isinstance(v, int):
#                 msg = 'Must be an integer'
#                 raise store.ValidationError(k, v, msg)

#         return v

#     def get_origins(self):
#         """Returns a list of configured origins.

#         This list is composed by plugin.Origin objects.
#         """

#         return list(map(
#             self.get_origin_for_origin_spec,
#             self.get_origins_specs()))

#     def get_origins_specs(self):
#         """Returns a list of configured origins in a specification form.

#         This list is composed by importer.OriginSpec objects which are
#         data-only structures. To get some usable object you may want to use
#         importer.Importer.get_origins method
#         """

#         defs = self.app.settings.get('origin', default={})
#         if not defs:
#             msg = "No origins defined"
#             self.app.logger.warning(msg)
#             return []

#         ret = []
#         for (name, params) in defs.items():
#             try:
#                 spec = OriginSpec(name, **params)
#                 ret.append(spec)
#             except TypeError:
#                 msg = "Invalid origin {name}"
#                 msg = msg.format(name=name)
#                 self.app.logger.warn(msg)

#         return ret

#     def get_search_providers(self, query_spec):
#         """Get autogenerated origins for a selector.QuerySpec object.

#         One query can produce zero or more or plugin.Origins from the activated
#         origin extensions.

#         Returned origins are configured with one iteration.
#         """

#         msg = "Discovering origins for {query}"
#         msg = msg.format(query=query_spec)
#         self.app.logger.info(msg)

#         impls = self.app.get_implementations(SearchProvider)
#         if not impls:
#             msg = ("There are no origin implementations available or none of "
#                    "them is enabled, check your configuration")
#             self.app.logger.warning(msg)
#             return []

#         ret = []
#         for (name, impl) in impls.items():
#             try:
#                 origin = impl(self.app, query_spec)
#                 ret.append(origin)
#                 msg = " Found compatible origin '{name}'"
#                 msg = msg.format(name=name)
#                 self.app.logger.info(msg)
#             except IncompatibleQueryError:
#                 pass

#         if not ret:
#             msg = "No compatible origins found for {query}"
#             msg = msg.format(query=query_spec)
#             self.app.logger.warning(msg)

#         print([x.get_search_parameters() for x in ret])

#         return ret

#     def get_origin_for_origin_spec(self, origin_spec):
#         backend = origin_spec.get('backend')
#         return self.app.get_extension(
#             Origin, backend,
#             origin_spec=origin_spec)

#     def _organize_data_by_most_recent(self, *src_data):
#         """
#         Organizes the input list of source data into a dict.
#         Keys will be the urn or permalink of the 'proto-sources'.
#         In case of duplicates the oldest is discarted
#         """
#         tmp = dict()

#         for sd in src_data:
#             k = sd['_discriminator']
#             assert k is not None

#             # If we got a duplicated urn keep the most recent
#             if k in tmp and (sd['created'] < tmp[k]['created']):
#                 continue

#             tmp[k] = sd

#         return tmp

#     def _get_sources_for_data(self, *psrcs):
#         # First thing to do is organize input data
#         psrcs = self._organize_data_by_most_recent(*psrcs)

#         # Check for existings sources
#         keys = list(psrcs.keys())
#         existing_srcs = self.app.db.session.query(models.Source).filter(
#             models.Source._discriminator.in_(keys)
#         ).all()

#         # Name change is special
#         name_updated_srcs = []

#         for src in existing_srcs:
#             src_data = psrcs[src._discriminator]

#             if src.name != src_data['name']:
#                 name_updated_srcs.append(src)

#             # Override srcs's properties with src_data properties
#             for key in src_data:
#                 if key == '_discriminator':
#                     continue

#                 # …except for 'created'
#                 # Some origins report created timestamps from heuristics,
#                 # variable or fuzzy data that is degraded over time.
#                 # For these reason we keep the first 'created' data as the most
#                 # fiable
#                 if key == 'created' and \
#                    src.created is not None and \
#                    src.created < src_data['created']:
#                     continue

#                 setattr(src, key, src_data[key])

#         # Check for missing sources
#         missing_discriminators = (
#             set(psrcs) -
#             set([x._discriminator for x in existing_srcs])
#         )

#         # Create new sources
#         created_srcs = [
#             models.Source.from_data(**psrcs[x])
#             for x in missing_discriminators
#         ]

#         # Create return data
#         ret = {x: [] for x in chain(existing_srcs, created_srcs)}

#         for x in created_srcs:
#             ret[x].append('created')

#         for x in existing_srcs:
#             ret[x].append('updated')

#         for x in created_srcs + name_updated_srcs:
#             ret[x].append('mediainfo-process-needed')

#         return list(ret.items())

#     def resolve_source(self, source):
#         # spec = OriginSpec(
#         #     name='x',
#         #     backend=source.provider,
#         #     url=source.uri,
#         #     iterations=1, type=None,
#         #     language=None)

#         # origin = self.get_origin_for_origin_spec(spec)
#         # buff = self.app.get_fetcher().fetch(source.uri)
#         # res = origin.parse(buff)

#         # if len(res) > 1:
#         #     msg = "Got more than one source. {backend} is not working properly"
#         #     msg = msg.format(backend=source.provider)
#         #     self.logger.warning(msg)

#         # res = results[0]
#         # res = origin._normalize_source_data(res)[0]

#         msg = "Resolve lazy-sources is not implemented yet (src)"
#         msg = msg.format(src=source)
#         raise ResolveError(msg)

#     def process(self, *origins):
#         """Core function for importer.Importer.

#         1. Iterate over the URLs produced by origin
#         2. Fetch URL and parse content
#         3. Process content thru origin parser to get models.Source object
#         4. Insert or update DB with those models.

#         Within this process the 'created' and 'last_seen' fields from
#         models.Source are set.

#         Some signals are emited:

#         - 'source-added'
#         - 'source-updated'
#         - 'sources-added-batch',
#         - 'sources-updated-batch',
#         """

#         # Get, sched and run all tasks from origins
#         self._sched = ImporterRunner(
#             maxtasks=self.app.settings.get('async-max-concurrency'),
#             timeout=self.app.settings.get('async-timeout'),
#             logger=self.app.logger.getChild('asyncsched'))

#         for origin in origins:
#             self._sched.sched(*origin.get_tasks())

#         self._sched.run()

#         # Keep the most recent data in case of duplicates
#         # psrcs = self._organize_data_by_most_recent(*self._sched.results)

#         # Get sources
#         srcs = self._get_sources_for_data(*self._sched.results)

#         # Disable scheduler
#         self._sched = None

#         rev_srcs = {
#             'added-sources': [],
#             'updated-sources': [],
#             'mediainfo-process-needed': [],
#         }

#         # Reverse source data structure
#         for (src, flags) in srcs:
#             if 'created' in flags:
#                 self.app.db.session.add(src)
#                 rev_srcs['added-sources'].append(src)

#             if 'updated' in flags:
#                 rev_srcs['updated-sources'].append(src)

#             if 'mediainfo-process-needed' in flags:
#                 rev_srcs['mediainfo-process-needed'].append(src)

#         if rev_srcs['mediainfo-process-needed']:
#             self.app.mediainfo.process(*rev_srcs['mediainfo-process-needed'])

#         self.app.db.session.commit()

#         # Launch signals
#         self.app.signals.send('sources-added-batch',
#                               sources=rev_srcs['added-sources'])

#         self.app.signals.send('sources-updated-batch',
#                               sources=rev_srcs['updated-sources'])

#         # Save data
#         self.app.db.session.commit()

#         self.app.logger.info('{n} sources created'.format(
#             n=len(rev_srcs['added-sources'])
#         ))
#         self.app.logger.info('{n} sources updated'.format(
#             n=len(rev_srcs['updated-sources'])
#         ))
#         self.app.logger.info('{n} sources parsed'.format(
#             n=len(rev_srcs['mediainfo-process-needed'])
#         ))

#         return srcs

#     def process_spec(self, origin_spec):
#         return self.process(
#             self.get_origin_for_origin_spec(origin_spec)
#         )

#     def process_query(self, query_spec):


#         search_providers = self.get_search_providers(query_spec)
#         search_parameters = [x.get_search_parameters()
#                              for x in search_providers]

#         import ipdb; ipdb.set_trace(); pass

#         return self.process(
#             *self.get_search_providers(query_spec)
#         )

#     def push_to_sched(self, *coros):
#         if not self._sched:
#             msg = "Scheduler not available at this phase"
#             self.app.error(msg)
#             return

#         self._sched.sched(*coros)

#     def run(self):
#         return self.process(*self.get_origins())


# class OriginSpec(utils.InmutableDict):
#     """Support class to store specification of an origin.

#     This class only stores information of an origin, it is not the origin.

#     Instances of importer.OriginSpec are used to get a configured plugin.Origin
#     from importer.Importer
#     """
#     def __init__(self, backend, url=None, iterations=1, type=None,
#                  language=None, name=None):
#         # Check strs
#         strs = [
#             ('name', name, True),
#             ('backend', backend, False),
#             ('url', url, True),
#             ('type', type, True),
#             ('language', language, True)
#         ]

#         for (nme, var, nullable) in strs:
#             if var is None and nullable:
#                 continue

#             if isinstance(var, str) and var != '':
#                 continue

#             msg = "Invalid value '{value}' for '{name}'. It must be a str"
#             msg = msg.format(name=nme, value=var)
#             raise TypeError(msg)

#         # Check ints
#         if not isinstance(iterations, int):
#             msg = "Invalid value '{value}' for '{name}'. It must be an int"
#             msg = msg.format(name='iterations', value=iterations)
#             raise TypeError(msg)

#         super().__init__(backend=backend, url=url, iterations=iterations,
#                          type=type, language=language, name=name)

#     def __repr__(self):
#         return 'OriginSpec({x}, backend={backend}, {iterations})'.format(
#             backend=self.get('backend'),
#             x=self.get('name') or self.get('url') or '(none)',
#             iterations=self.get('iterations'))

# class Origin(extension.Extension):
#     """Extension point for implemented Origin extension.

#     Origin extensions are responsible to parse websites or fetch information
#     from other services.

#     They must override or implement:

#     - class attribute BASE_URL: Default URL (or URI) of website. This URL will
#         be used if no other is specified
#     - class attribute PROVIDER_NAME: Unique (among other ext.Origin
#         implementations) identifier
#     - method process_buffer: Given a utf8 buffer this function should return a
#         list of dicts with found information. Those dicts can containing the
#         same fields present in models.Source, only name and uri are mandatory

#     They can override:

#     - method paginate: Given a URL returns a generator object which yields that
#         URL and subsequent URLs
#     - method get_query_url: Given a selector.QuerySpec object returns the URL
#         containing that search result for the website that ext.Origin
#         implements

#     This class also contains some helper methods for child classes, check docs
#     or code for more information.
#     """

#     def __init__(self, app, spec, logger=None):
#         assert isinstance(app, core.Arroyo)
#         assert isinstance(spec, OriginSpec)

#         super(Origin, self).__init__(app)

#         self.spec = spec
#         self.logger = logger or app.logger.getChild(self.PROVIDER_NAME)

#         self._name = origin_spec['name']
#         self._url = origin_spec['url'] or self.BASE_URL
#         self._iterations = origin_spec['iterations']
#         self._overrides = {k: v for (k, v) in {
#             'type': origin_spec['type'],
#             'language': origin_spec['language'],
#         }.items() if v is not None}

#     @property
#     def iterations(self):
#         return self._iterations

#     def urls(self):
#         """
#         Generator that provides URLs from origin
#         """
#         if not self._url:
#             return

#         iters = max(1, self._iterations)

#         g = self.paginate(self._url)
#         return (next(g) for x in range(iters))

#     def paginate_by_query_param(self, url, key, default=1):
#         """
#         Utility generator for easy pagination
#         """
#         def alter_param(k, v):
#             if k == key:
#                 try:
#                     v = int(v) + 1
#                 except ValueError:
#                     v = default

#                 v = str(v)

#             return k, v

#         yield url

#         parsed = parse.urlparse(url)
#         qsl = parse.parse_qsl(parsed.query)
#         if key not in [x[0] for x in qsl]:
#             qsl = qsl + [(key, default)]

#         while True:
#             qsl = [alter_param(*x) for x in qsl]
#             yield parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path,
#                                     parsed.params,
#                                     parse.urlencode(qsl, doseq=True),
#                                     parsed.fragment))

#     def get_query_url(self, query):
#         return

#     def get_tasks(self):
#         return [self.process(url) for url in self.urls()]

#     @asyncio.coroutine
#     def fetch(self, url):
#         s = self.app.settings

#         fetcher = fetchers.AIOHttpFetcher(
#             logger=self.logger.getChild('fetcher'),
#             **{
#                 k.replace('-', '_'): v
#                 for (k, v) in s.get('fetcher').items()
#             })
#         buff = yield from fetcher.fetch(url)

#         return buff

#     @asyncio.coroutine
#     def process(self, url):
#         """
#         Coroutine that fetches and parses an URL
#         """
#         msg = "Fetching «{url}»"
#         msg = msg.format(url=url)
#         self.app.logger.info(msg)

#         try:
#             buff = yield from self.fetch(url)

#         except asyncio.CancelledError as e:
#             msg = "Fetch cancelled '{url}' (possibly timeout)"
#             msg = msg.format(url=url)
#             self.app.logger.error(msg)
#             return []

#         except aiohttp.errors.ClientOSError as e:
#             msg = "Client error fetching {url}: {e}"
#             msg = msg.format(url=url, e=e)
#             self.app.logger.error(msg)
#             return []

#         except Exception as e:
#             msg = "Unhandled exception {type}: {e}"
#             msg = msg.format(type=type(e), e=e)
#             self.app.logger.critical(msg)
#             raise

#         psrcs = self.parse(buff)
#         psrcs = self._normalize_source_data(*psrcs)
#         if isinstance(psrcs, (filter, map)):
#             psrcs = list(psrcs)

#         msg = "Found {n_srcs_data} sources in {url}"
#         msg = msg.format(n_srcs_data=len(psrcs), url=url)
#         self.app.logger.info(msg)

#         return psrcs

#     def _normalize_source_data(self, *psrcs):
#         required_keys = set([
#             'name',
#             'provider',
#             'uri',
#         ])
#         allowed_keys = required_keys.union(set([
#             'created',
#             'language',
#             'leechers',
#             'seeds',
#             'size',
#             'type'
#         ]))

#         ret = []
#         now = utils.now_timestamp()

#         for psrc in psrcs:
#             if not isinstance(psrc, dict):
#                 msg = "Origin «{name}» emits invalid data type: {datatype}"
#                 msg = msg.format(name=self.PROVIDER_NAME,
#                                  datatype=str(type(psrc)))
#                 self.app.logger.error(msg)
#                 continue

#             # Insert provider name
#             psrc['provider'] = self.PROVIDER_NAME

#             # Apply overrides
#             psrc.update(self._overrides)

#             # Check required keys
#             missing_keys = required_keys - set(psrc.keys())
#             if missing_keys:
#                 msg = ("Origin «{name}» doesn't provide the required "
#                        "following keys: {missing_keys}")
#                 msg = msg.format(name=self.PROVIDER_NAME,
#                                  missing_keys=missing_keys)
#                 self.app.logger.error(msg)
#                 continue

#             # Only those keys are allowed
#             forbiden_keys = [k for k in psrc if k not in allowed_keys]
#             if forbiden_keys:
#                 msg = ("Origin «{name}» emits the following invalid "
#                        "properties for its sources: {forbiden_keys}")
#                 msg = msg.format(name=psrc['provider'],
#                                  forbiden_keys=forbiden_keys)
#                 self.app.logger.warning(msg)

#             psrc = {k: psrc.get(k, None) for k in allowed_keys}

#             # Check value types
#             checks = [
#                 ('created', int),
#                 ('leechers', int),
#                 ('name', str),
#                 ('seeds', int),
#                 ('size', int),
#                 ('permalink', str),
#                 ('uri', str),
#             ]
#             for k, kt in checks:
#                 if (psrc.get(k) is not None) and (not isinstance(psrc[k], kt)):
#                     try:
#                         psrc[k] = kt(psrc[k])
#                     except (TypeError, ValueError):
#                         msg = ("Origin «{name}» emits invalid «{key}» value. "
#                                "Expected {expectedtype} (or compatible), got "
#                                "{currtype}")
#                         msg = msg.format(
#                             name=self.PROVIDER_NAME, key=k,
#                             expectedtype=kt, currtype=str(type(psrc[k])))
#                         self.app.logger.error(msg)
#                         continue

#             # Calculate URN from uri. If not found its a lazy source
#             # IMPORTANT: URN is **lowercased** and **sha1-encoded**
#             try:
#                 qs = parse.urlparse(psrc['uri']).query
#                 urn = parse.parse_qs(qs)['xt'][-1]
#                 urn = urn.lower()
#                 sha1urn, b64urn = downloads.calculate_urns(urn)
#                 psrc['urn'] = sha1urn
#             except KeyError:
#                 pass

#             # Fix created
#             psrc['created'] = psrc.get('created', None) or now

#             # Set discriminator
#             psrc['_discriminator'] = psrc.get('urn') or psrc.get('uri')
#             assert(psrc['_discriminator'] is not None)

#             # Append to ret value
#             ret.append(psrc)

#         return ret

#     def __repr__(self):
#         return "<%s (%s)>" % (
#             self.__class__.__name__,
#             getattr(self, '_url', '(None)'))


# class SearchProvider(extension.Extension, metaclass=abc.ABCMeta):
#     NAME = 'Base'

#     def __init__(self, app, query_spec):
#         super().__init__(app)
#         self.params = query_spec  # Isolate plugins from internal details

#     @abc.abstractmethod
#     def get_search_parameters(self):
#         """Build remote search parameters from initial search params.

#         Must return None or a SearchParameters object
#         """
#         return None


# class SearchParameters(collections.namedtuple(
#                        '_SearchResult', ['backend', 'url', 'params'])):

#     def __new__(cls, backend, url, params={}):
#         if not isinstance(backend, str) or str == '':
#             raise TypeError('backend must be a non-empty string')

#         if not isinstance(url, str) or str == '':
#             raise TypeError('url must be a non-empty string')

#         if params is not None and not isinstance(params, dict):
#             raise TypeError('params must be None or a dict')

#         return super(SearchParameters, cls).__new__(cls, backend, url, params)
