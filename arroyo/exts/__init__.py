from urllib import parse


class Extension:
    def __init__(self, app):
        self.app = app
        super(Extension, self).__init__()


class Service(Extension):
    pass


class Origin(Extension):
    def __init__(self, app, origin_def):
        super(Origin, self).__init__(app)

        self._url = origin_def.url
        self._iteration = 0
        self._iterations = origin_def.iterations
        self._overrides = {k: v for (k, v) in {
            'type': origin_def.type,
            'language': origin_def.language,
            'provider': origin_def.backend
        }.items() if v is not None}

    @property
    def iteration(self):
        return self._iteration

    def get_urls(self):
        iterations = max(1, self._iterations)
        g = self.url_generator(self._url)
        for itr in range(0, iterations):
            self._iteration += 1
            yield next(g)

    def process(self, buff):
        def _fix(src):
            src['urn'] = parse.parse_qs(
                parse.urlparse(src['uri']).query)['xt'][-1]

            src.update(self._overrides)
            return src

        return list(map(_fix, self.process_buffer(buff)))

    def search(self, query):
        yield None

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


def argument(*args, **kwargs):
    """argparse argument wrapper to ease the command argument definitions"""
    def wrapped_arguments():
        return args, kwargs

    return wrapped_arguments
