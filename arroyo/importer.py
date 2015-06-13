# from glob import fnmatch
from ldotcommons import fetchers

from arroyo import (exc, models)

_NoneType = type(None)


def _origin_ns_validator(k, v):
    parts = k.split('.')
    if len(parts) != 3:
        return v

    k = parts[-1]

    msg = "Invalid value '{}' for '{}'. Must be '{}'"

    if k == 'backend':
        if v is None or not isinstance(v, str) or v == '':
            raise TypeError(msg.format(v, k, str))

    if k in ['url', 'language', 'type']:
        if not isinstance(v, (_NoneType, str)) or v == '':
            raise TypeError(msg.format(v, k, str))

    if k == 'iterations':
        if v is None:
            v = 1
        elif not isinstance(k, int):
            try:
                v = int(v)
            except ValueError:
                v = 1

    return v


class OriginSpec:
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

        # Check int
        if not isinstance(iterations, int):
            msg = "Invalid value '{value}' for '{name}'. It must be an int"
            msg = msg.format(name='iterations', value=iterations)
            raise TypeError(msg)

        self.backend = backend
        self.url = url
        self.iterations = iterations or 1
        self.type = type
        self.language = language
        self.name = name

    # Read-only attributes
    def __setattr__(self, attr, value):
        if hasattr(self, 'name'):
            msg = "Attribute {name} is read only"
            msg = msg.format(name=attr)
            raise TypeError(msg)
        else:
            super(OriginSpec, self).__setattr__(attr, value)

    def __repr__(self):
        return "<{pkg}.{clsname}: '{name}'>".format(
            pkg=__name__,
            clsname=self.__class__.__name__,
            name=getattr(self, 'name', '(null)'))


class Importer:
    def __init__(self, app):
        self.app = app
        self.app.settings.set_validator(
            _origin_ns_validator,
            ns='origin')

        self._logger = app.logger.getChild('importer')
        app.signals.register('source-added')
        app.signals.register('source-updated')
        app.signals.register('sources-added-batch')
        app.signals.register('sources-updated-batch')

    def get_origin_specs(self):
        specs = []

        for (name, params) in self.app.settings.get_tree('origin').items():
            try:
                specs.append(OriginSpec(name, params.pop('backend'), **params))
            except TypeError:
                self.app.logger.warn('Invalid origin {}'.format(name))

        return specs

    def execute(self):
        for spec in self.get_origin_specs():
            origin = self.app.get_extension('origin', spec.backend,
                                            origin_spec=spec)
            self._import(origin)

    # def get_origin_defs(self):
    #     origin_defs = []

    #     for (name, params) in self.app.settings.get('origin').items():
    #         try:
    #             backend = params['backend']
    #         except KeyError:
    #             msg = 'Origins {name} has no backend defined'
    #             self._logger.error(msg.format(name=name))
    #             continue

    #         origin_defs.append(OriginDefinition(
    #             name=name,
    #             backend=backend,
    #             url=params.get('seed_url'),
    #             iterations=params.get('iterations', default=1),
    #             type=params.get('type', default=None),
    #             language=params.get('language', default=None)))

    #     return origin_defs

    def get_origin(self, origin_def):
        return self.app.get_extension('origin', origin_def.backend,
                                      origin_def=origin_def)

    def import_query(self, query_def):
        for (name, impl) in self.app.get_implementations('origin').items():
            origin = impl(self.app, query_spec=query_def)
            self._import(origin)

    def import_origin(self, origin_def):
        origin = self.get_origin(origin_def)
        self._import(origin)

    def _import(self, origin):
        sources = []
        for url in origin.get_urls():
            msg = "{name} {iteration}/{iterations}: {url}"
            self._logger.debug(msg.format(
                name=origin.PROVIDER_NAME,
                iteration=origin.iteration,
                iterations=origin.iterations,
                url=url))

            try:
                buff = self.app.fetcher.fetch(url)
            except fetchers.FetchError as e:
                msg = 'Unable to retrieve {url}: {msg}'
                msg = msg.format(url=url, msg=e)
                self._logger.warning(msg)
                continue

            try:
                srcs = origin.process(buff)
            except exc.ProcessException as e:
                msg = "Unable to process '{url}': {error}"
                msg = msg.format(url=url, error=e)
                self._logger.error(msg)
                continue

            if not srcs:
                msg = "No sources found in '{url}'"
                msg = msg.format(url=url)
                self._logger.warning(msg)
                continue

            msg = "Found {n} source(s) in '{url}'"
            msg = msg.format(n=len(srcs), url=url)
            self._logger.info(msg)

            sources += srcs

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
