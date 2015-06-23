from urllib import parse

from ldotcommons import utils


class Extension:
    def __init__(self, app):
        super(Extension, self).__init__()
        self.app = app


class Service(Extension):
    pass


class Origin(Extension):
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

        def fix_data(psrc):
            if not isinstance(psrc, dict):
                return None

            # Apply overrides
            psrc.update(self._overrides)

            # Trim-down protosrc
            psrc = {k: psrc.get(k, None) for k in [
                'name', 'uri', 'timestamp', 'size', 'seeds', 'leechers',
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
            for k in ['timestamp', 'size', 'seeds', 'leechers']:
                if not isinstance(psrc[k], int):
                    try:
                        psrc[k] = int(psrc[k])
                    except (TypeError, ValueError):
                        psrc[k] = None

            # Fix timestamp
            psrc['timestamp'] = psrc.get('timestamp', None) or now
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
    pass


class Downloader(Extension):
    pass


class Selector(Extension):
    pass


class CronTask(Extension):
    def __init__(self, app):
        if not hasattr(self, 'INTERVAL'):
            msg = "{class_name} doesn't have a valid INTERVAL attribute"
            msg = msg.format(class_name=self.__class__.__name__)
            raise TypeError(msg)

        try:
            self.INTERVAL = utils.parse_time(self.INTERVAL)
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
