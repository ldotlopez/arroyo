from ldotcommons import utils
from urllib import parse


class Extension:
    """Basic extension point.
    Its reponsability is to create a link in ext.Extension with core.Arroyo
    """
    def __init__(self, app):
        super(Extension, self).__init__()
        self.app = app


class Service(Extension):
    pass


class Origin(Extension):
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
    or code for more information
    """

    def __init__(self, app, origin_spec=None, query_spec=None):
        super(Origin, self).__init__(app)

        if origin_spec and query_spec:
            msg = 'origin_spec and query_spec are mutually exclusive'
            raise ValueError(msg)

        self._iteration = 0

        if origin_spec:
            self._name = origin_spec['name']
            self._url = origin_spec['url'] or self.BASE_URL
            self._iterations = origin_spec['iterations']
            self._overrides = {k: v for (k, v) in {
                'type': origin_spec['type'],
                'language': origin_spec['language'],
            }.items() if v is not None}

        else:
            self._name = 'internal query'
            self._url = self.get_query_url(query_spec)
            self._iterations = 1
            self._overrides = {}

    @property
    def iteration(self):
        return self._iteration

    @property
    def iterations(self):
        return self._iterations

    def get_urls(self):
        if not self._url:
            return

        iterations = max(1, self._iterations)
        g = self.paginate(self._url)
        while self._iteration < iterations:
            self._iteration += 1
            yield next(g)

    def get_query_url(self, query):
        return

    def process(self, buff):
        """
        Get protosources from origin. Integrity of collected data is guaranteed
        """
        now = utils.now_timestamp()

        deprecated_warn = False

        def fix_data(psrc):
            nonlocal deprecated_warn

            if not isinstance(psrc, dict):
                return None

            # Apply overrides
            psrc.update(self._overrides)

            # Trim-down protosrc
            if 'timestamp' in psrc and not deprecated_warn:
                msg = ("Provider {provider} is using deprecated field "
                       "«timestamp»")
                msg = msg.format(provider=self.PROVIDER_NAME)
                self.app.logger.warning(msg)
                deprecated_warn = True

            psrc = {k: psrc.get(k, None) for k in [
                'name', 'uri', 'created', 'size', 'seeds', 'leechers',
                'language', 'type'
            ]}

            # Calculate URN
            try:
                psrc['urn'] = parse.parse_qs(
                    parse.urlparse(psrc['uri']).query)['xt'][-1]
            except (IndexError, KeyError):
                return None

            # Check strings fields
            for k in ['urn', 'name', 'uri']:
                if not isinstance(psrc[k], str):
                    return None

            # Fix and check integer fields
            for k in ['created', 'size', 'seeds', 'leechers']:
                if not isinstance(psrc[k], int):
                    try:
                        psrc[k] = int(psrc[k])
                    except (TypeError, ValueError):
                        psrc[k] = None

            # Fix created
            psrc['created'] = psrc.get('created', None) or now

            psrc['provider'] = self.PROVIDER_NAME

            # All done
            return psrc

        def filter_incomplete(psrc):
            if not isinstance(psrc, dict):
                return False

            needed = ['name', 'uri', 'urn']
            return all((isinstance(psrc.get(x, None), str) for x in needed))

        ret = self.process_buffer(buff)
        ret = map(fix_data, ret)
        ret = filter(filter_incomplete, ret)

        return list(ret)

    def paginate_by_query_param(self, url, key, default=1):
        parsed = parse.urlparse(url)
        parsed_qs = parse.parse_qs(parsed.query)
        try:
            page = int(parsed_qs.pop(key, [str(default)])[0])
        except ValueError:
            page = 1

        while True:
            parsed_qs[key] = str(page)
            yield parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path,
                                    parsed.params,
                                    parse.urlencode(parsed_qs, doseq=True),
                                    parsed.fragment))
            page += 1

    def __repr__(self):
        return "<%s (%s)>" % (
            self.__class__.__name__,
            getattr(self, '_url', '(None)'))


class Command(Extension):
    help = ''
    arguments = ()

    def run(self, arguments):
        raise NotImplementedError()


class Downloader(Extension):
    def add(self, source, **kwargs):
        raise NotImplementedError()

    def remove(self, source, **kwargs):
        raise NotImplementedError()

    def list(self, **kwargs):
        raise NotImplementedError()

    def get_state(self, source, **kwargs):
        raise NotImplementedError()

    def translate_item(self, backend_obj):
        raise NotImplementedError()


class Filter(Extension):
    HANDLES = ()

    @classmethod
    def compatible(cls, model, key):
        return model == cls.APPLIES_TO and key in cls.HANDLES

    def __init__(self, app, key, value):
        super().__init__(app)
        self.key = key
        self.value = value

    def filter(self, x):
        raise NotImplementedError()

    def apply(self, iterable):
        return filter(self.filter, iterable)

    def alter_query(self, qs):
        raise NotImplementedError()


class Sorter(Extension):
    def sort(self, sources):
        return sources


class QuerySpec(utils.InmutableDict):
    def __init__(self, query_name, **kwargs):
        def _normalize_key(key):
            for x in [' ', '_']:
                key = key.replace(x, '-')
            return key

        kwargs = {_normalize_key(k): v for (k, v) in kwargs.items()}
        kwargs['kind'] = kwargs.get('kind', 'source')

        if 'language' in kwargs:
            kwargs['language'] = kwargs['language'].lower()

        if 'type' in kwargs:
            kwargs['type'] = kwargs['type'].lower()

        super().__init__(**kwargs)
        self._name = query_name

    @property
    def name(self):
        return self._name


class Query(Extension):
    def __init__(self, app, spec):
        super().__init__(app)
        self._spec = spec
        self.params = utils.InmutableDict(spec.exclude('kind'))

    @property
    def name(self):
        return self.spec.name

    @property
    def spec(self):
        return self._spec

    def matches(self, include_all=False):
        raise NotImplementedError()

    # def selection(self, matches):
    #     try:
    #         return matches[0]
    #     except IndexError:
    #         return None


class CronTask(Extension):
    def __init__(self, app):
        if not hasattr(self, 'INTERVAL'):
            msg = "{class_name} doesn't have a valid INTERVAL attribute"
            msg = msg.format(class_name=self.__class__.__name__)
            raise TypeError(msg)

        try:
            self.INTERVAL = utils.parse_interval(self.INTERVAL)
        except ValueError as e:
            msg = "Invalid interval value '{interval}', check docs"
            msg = msg.format(interval=self.INTERVAL)
            raise TypeError(msg) from e

        if not hasattr(self, 'NAME') or \
           not isinstance(self.NAME, str) or \
           self.NAME == "":
            msg = "{class_name} doesn't have a valid NAME attribute"
            msg = msg.format(class_name=self.__class__.__name__)
            raise TypeError(msg)

        super().__init__(app)

        self.name = self.__class__.__name__.lower()
        self.app = app
        self.keys = {
            'registered': 'crontask.%s.registered' % self.NAME,
            'last-run': 'crontask.%s.last-run' % self.NAME
        }

    @property
    def last_run(self):
        return self.app.variables.get(self.keys['last-run'], 0)

    @property
    def should_run(self):
        return utils.now_timestamp() - self.last_run >= self.INTERVAL

    def run(self):
        self.app.variables.set(
            self.keys['last-run'],
            utils.now_timestamp())


def argument(*args, **kwargs):
    """argparse argument wrapper to ease the command argument definitions"""
    def wrapped_arguments():
        return args, kwargs

    return wrapped_arguments
