import collections
from ldotcommons import fetchers

from arroyo import (exc, models)


_UA = 'Mozilla/5.0 (X11; Linux x86) Home software (KHTML, like Gecko)'

OriginDefinition = collections.namedtuple('OriginDefinition', (
    'name', 'backend', 'url', 'iterations', 'type', 'language'
))


class Importer:
    def __init__(self, app):
        self.app = app
        self._logger = app.logger.getChild('importer')
        app.signals.register('source-added')
        app.signals.register('source-updated')
        app.signals.register('sources-added-batch')
        app.signals.register('sources-updated-batch')

    def get_origin_defs(self):
        origin_defs = []

        for (name, params) in self.app.config_subdict('origin').items():
            try:
                backend = params['backend']
            except KeyError:
                msg = 'Origins {name} has no backend defined'
                self._logger.error(msg.format(name=name))
                continue

            origin_defs.append(OriginDefinition(
                name=name,
                backend=backend,
                url=params.get('seed_url'),
                iterations=int(params.get('iterations', 1)),
                type=params.get('type'),
                language=params.get('language')))

        return origin_defs

    def get_origin(self, origin_def):
        return self.app.get_extension('origin', origin_def.backend,
                                      origin_def=origin_def)

    def import_query(self, query_def):
        for (name, impl) in self.app.get_implementations('origin').items():
            origin = impl(self.app, query_def=query_def)
            self._import(origin)

    def import_origin(self, origin_def):
        origin = self.get_origin(origin_def)
        self._import(origin)

    def _import(self, origin):
        fetcher = fetchers.UrllibFetcher(
            cache=True, cache_delta=60 * 20, headers={'User-Agent': _UA},
            logger=self._logger.getChild('fetcher'))

        sources = []
        for url in origin.get_urls():
            msg = "{name} {iteration}/{iterations}: {url}"
            self._logger.debug(msg.format(
                name=origin.name,
                iteration=origin.iteration,
                iterations=origin.iterations,
                url=url))

            try:
                buff = fetcher.fetch(url)
            except fetchers.FetchError as e:
                msg = 'Unable to retrieve {url}: {msg}'
                msg = msg.format(url=url, msg=e)
                self._logger.warning(msg)
                continue

            try:
                sources += origin.process(buff)
            except exc.ProcessException as e:
                msg = "Unable to process '{url}': {error}"
                msg = msg.format(url=url, error=e)
                self._logger.error(msg)
                continue

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
