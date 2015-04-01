from urllib import parse


class Extension:
    def __init__(self, app):
        super(Extension, self).__init__()
        self.app = app


class Service(Extension):
    pass


class Origin(Extension):
    def __init__(self, app, origin_def=None, query_def=None):
        super(Origin, self).__init__(app)

        if origin_def and query_def:
            raise ValueError('origin_def and query_def are mutually exclusive')

        self._iteration = 0

        if origin_def:
            self._name = origin_def.name
            self._url = origin_def.url or self.BASE_URL
            self._iterations = origin_def.iterations
            self._overrides = {k: v for (k, v) in {
                'type': origin_def.type,
                'language': origin_def.language,
                'provider': origin_def.backend
            }.items() if v is not None}

        else:
            clsname = self.__class__.__name__
            provider = clsname.split('.')[-1].lower()

            self._name = 'internal query'
            self._url = self.get_query_url(query_def)
            self._iterations = 1
            self._overrides = {
                'provider': provider
            }

    @property
    def name(self):
        return self._name

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
        def _fix(src):
            src['urn'] = parse.parse_qs(
                parse.urlparse(src['uri']).query)['xt'][-1]
            src.update(self._overrides)
            return src

        return list(map(_fix, self.process_buffer(buff)))

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
            self._url)


class Command(Extension):
    pass


class Downloader(Extension):
    pass


class Selector(Extension):
    pass


class Cron(Extension):
    def run(self):
        raise NotImplementedError()


def argument(*args, **kwargs):
    """argparse argument wrapper to ease the command argument definitions"""
    def wrapped_arguments():
        return args, kwargs

    return wrapped_arguments
