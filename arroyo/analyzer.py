import collections
from urllib import parse
from ldotcommons import fetchers, logging

from arroyo import models

_logger = logging.get_logger('analyzer')
_UA = 'Mozilla/5.0 (X11; Linux x86) Home software (KHTML, like Gecko)'

Origin = collections.namedtuple('Origin', (
    'name', 'importer', 'url', 'iterations', 'type', 'language'
))


class Importer:
    def __init__(self, backend, origin):
        self._backend = backend
        self._origin = origin
        self._iteration = 0
        self._overrides = {k: v for (k, v) in {
            'type': origin.type,
            'language': origin.language,
            'provider': origin.importer
        }.items() if v is not None}

    @property
    def iteration(self):
        return self._iteration

    def get_urls(self):
        iterations = max(1, self._origin.iterations)
        g = self._backend.url_generator(self._origin.url)
        for itr in range(0, iterations):
            self._iteration += 1
            yield next(g)

    def process(self, buff):
        def _fix(src):
            src['urn'] = parse.parse_qs(
                parse.urlparse(src['uri']).query)['xt'][-1]

            src.update(self._overrides)
            return src

        return list(map(_fix, self._backend.process(buff)))

    def __repr__(self):
        return "<%s (%s)>" % (
            self.__class__.name,
            self._backend.__class__.name)


class Analyzer:
    def __init__(self, app):
        self.app = app
        app.signals.register('source-added')
        app.signals.register('source-updated')
        app.signals.register('sources-added-batch')
        app.signals.register('sources-updated-batch')

    def get_origins(self):
        origins = []

        for (name, params) in self.app.config_subdict('origin').items():
            try:
                importer = params['importer']
            except KeyError:
                msg = 'Origins {name} has no analyzer defined'
                _logger(msg.format(name=name))
                continue

            origins.append(Origin(
                name=name,
                importer=importer,
                url=params.get('seed_url'),
                iterations=int(params.get('iterations', 1)),
                type=params.get('type'),
                language=params.get('language')))

        return origins

    def get_importer(self, origin):
        backend = self.app.get_implementation('importer', origin.importer)()
        return Importer(backend, origin)

    def analyze(self, origin):
        importer = self.get_importer(origin)

        fetcher = fetchers.UrllibFetcher(
            cache=True, cache_delta=60 * 20, headers={'User-Agent': _UA})

        sources = []
        for url in importer.get_urls():
            msg = "{origin}: iteration {iteration}: {url}"
            _logger.debug(msg.format(
                origin=origin.name,
                iteration=importer.iteration,
                iterations=origin.iterations,
                url=url))

            sources += importer.process(fetcher.fetch(url))

        ret = {
            'added-sources': [],
            'updated-sources': [],
        }

        for src in sources:
            obj, created = self.app.db.get_or_create(models.Source,
                                                     urn=src['urn'])
            for key in src:
                setattr(obj, key, src[key])

            if created:
                self.app.db.session.add(obj)

            signal_name = 'source-added' if created else 'source-updated'
            self.app.signals.send(signal_name, source=obj)

            batch_key = 'added-sources' if created else 'updated-sources'
            ret[batch_key].append(obj)

        self.app.signals.send('sources-added-batch',
                              sources=ret['added-sources'])
        self.app.signals.send('sources-updated-batch',
                              sources=ret['updated-sources'])

        self.app.db.session.commit()

        return ret
