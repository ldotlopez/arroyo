from ldotcommons import fetchers, utils

from arroyo import (exts, exc, models)


class OriginSpec(utils.InmutableDict):
    """Support class to store specification of an origin.

    This class only stores information of an origin, it is not the origin.

    Instances of importer.OriginSpec are used to get a configured exts.Origin
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


class Importer:
    """API for import.
    """

    def __init__(self, app):
        self.app = app
        self.app.settings.set_validator(
            self._origin_ns_validator,
            ns='origin')

        self._logger = app.logger.getChild('importer')
        app.signals.register('source-added')
        app.signals.register('source-updated')
        app.signals.register('sources-added-batch')
        app.signals.register('sources-updated-batch')

        app.register('crontask', 'importer', ImporterCronTask)

    @staticmethod
    def _origin_ns_validator(k, v):
        # Supported keys are:
        #
        # origin.*.backend (str)
        # origin.*.url (str, NoneType)
        # origin.*.iterations (int, NoneType =>1)
        # origin.*.type (str, NoneType)
        # origin.*.language (str, NoneType)

        parts = k.split('.')
        if len(parts) != 3:
            return v

        k = parts[-1]

        msg = "Invalid value '{}' for '{}'. Must be '{}'"

        if k == 'backend':
            if v is None or not isinstance(v, str) or v == '':
                raise TypeError(msg.format(v, k, str))

        if k in ['url', 'language', 'type']:
            if not isinstance(v, (utils.NoneType, str)) or v == '':
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

    def get_origins(self):
        """Returns a list of configured origins.

        This list is composed by exts.Origin objects.
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

        defs = self.app.settings.get_tree('origin', {})
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

        One query can produce zero or more or exts.Origins from the activated
        origin extensions.

        Returned origins are configured with one iteration.
        """

        impls = self.app.get_implementations('origin')
        if not impls:
            msg = ("There are no origin implementations available or none of "
                   "them is enabled, check your configuration")
            self.app.logger.warning(msg)
            return []

        ret = []
        for (name, impl) in impls.items():
            origin = impl(self.app, query_spec=query_spec)
            ret.append(origin)

        return ret

    def get_origin_for_origin_spec(self, origin_spec):
        backend = origin_spec.get('backend')
        return self.app.get_extension(
            'origin', backend, origin_spec=origin_spec)

    def import_origin(self, origin):
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

        sources = []
        errors = {}

        for url in origin.get_urls():
            msg = "{name} {iteration}/{iterations}: {url}"
            self._logger.debug(msg.format(
                name=origin.PROVIDER_NAME,
                iteration=origin.iteration,
                iterations=origin.iterations,
                url=url))
            errors[url] = None

            try:
                buff = self.app.fetcher.fetch(url)
            except fetchers.FetchError as e:
                msg = 'Unable to retrieve {url}: {msg}'
                msg = msg.format(url=url, msg=e)
                self._logger.warning(msg)
                errors[url] = e
                continue

            try:
                srcs = origin.process(buff)
            except exc.ProcessException as e:
                msg = "Unable to process '{url}': {error}"
                msg = msg.format(url=url, error=e)
                self._logger.error(msg)
                errors[url] = e
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
            'errors': errors
        }

        now = utils.now_timestamp()

        for src in sources:
            obj, created = self.app.db.get_or_create(models.Source,
                                                     urn=src['urn'])
            for key in src:
                setattr(obj, key, src[key])

            if created:
                obj.created = now
                obj.last_seen = now
                self.app.db.session.add(obj)
            else:
                obj.last_seen = now

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

    def import_origin_spec(self, origin_spec):
        origin = self.get_origin_for_origin_spec(origin_spec)
        return self.import_origin(origin)

    def import_query_spec(self, query_spec):
        origins = self.get_origins_for_query_spec(query_spec)
        for origin in origins:
            self.import_origin(origin)

    def run(self):
        for origin in self.get_origins():
            self.import_origin(origin)


class ImporterCronTask(exts.CronTask):
    NAME = 'importer'
    INTERVAL = '3H'

    def run(self):
        self.app.importer.run()
        super().run()
