import contextlib
import hashlib
import os
import sys
from appkit import utils
from urllib import parse


from arroyo import core, models


class TestApp(core.Arroyo):
    def __init__(self, d={}):
        settings = {
            'async-max-concurrency': 1,
            'async-timeout': sys.maxsize,
            'auto-cron': False,
            'auto-import': False,
            'db-uri': 'sqlite:///:memory:',
            'downloader': 'mock',
            'fetcher.cache-delta': 0,
            'fetcher.enable-cache': False,
            'fetcher.headers': {
                'User-Agent':
                    'Mozilla/5.0 (X11; Linux x86) Home software '
                    '(KHTML, like Gecko)',
            },
            'importer.parser': 'auto',
            'log-format': '%(message)s',
            'log-level': 'WARNING',
            'selector.sorter': 'basic',
        }
        settings.update(d)
        settings = core.ArroyoStore(settings)

        super().__init__(settings)

    def insert_sources(self, *srcs):
        for src in srcs:
            if isinstance(src, str):
                src = mock_source(src)

            elif callable(src):
                name, kwargs = src()
                src = mock_source(name, **kwargs)

            elif isinstance(src, models.Source):
                pass

            self.db.session.add(src)

        with_type = [x for x in srcs if x.type]
        if with_type:
            self.mediainfo.process(*with_type)

        self.db.session.commit()

    @contextlib.contextmanager
    def hijack(self, obj, attr, value):
        orig = getattr(obj, attr)
        setattr(obj, attr, value)
        yield
        setattr(obj, attr, orig)


def mock_source(name, **kwargs):
    if 'urn' not in kwargs:
        kwargs['urn'] = \
            'urn:btih:' + hashlib.sha1(name.encode('utf-8')).hexdigest()

    if 'uri' not in kwargs:
        kwargs['uri'] = 'magnet:?xt={urn}&dn={dn}'.format(
            urn=kwargs['urn'],
            dn=parse.quote_plus(name))

    kwargs.pop('_discriminator', None)

    now = utils.now_timestamp()
    kwargs['created'] = kwargs.get('created', now)
    kwargs['last_seen'] = kwargs.get('last_seen', now)

    if 'provider' not in kwargs:
        kwargs['provider'] = 'mock'

    return models.Source(name=name, **kwargs)


def www_sample_path(sample):
    thisfile = os.path.realpath(__file__)
    return os.path.join(os.path.dirname(thisfile), "www-samples", sample)
