import contextlib
import os
import sys


from arroyo import core, models


class TestApp(core.Arroyo):
    def __init__(self, d={}):
        settings = {
            'async-max-concurrency': 1,
            'async-timeout': sys.maxsize,
            'auto-cron': False,
            'auto-import': False,
            'db-uri': 'sqlite:///:memory:',
            'downloader.backend': 'mock',
            'log-format': '%(message)s',
            'log-level': 'WARNING',
            'selector.sorter': 'basic'
        }
        settings.update(d)
        settings = core.ArroyoStore(settings)

        super().__init__(settings)

    def insert_sources(self, *srcs):
        for src in srcs:
            if isinstance(src, str):
                src = models.Source.from_data(src)

            elif callable(src):
                name, kwargs = src()
                src = models.Source.from_data(name, **kwargs)

            elif isinstance(src, models.Source):
                pass

            self.db.session.add(src)
            if src.type:
                self.mediainfo.process(src)

        self.db.session.commit()

    @contextlib.contextmanager
    def hijack(self, obj, attr, value):
        orig = getattr(obj, attr)
        setattr(obj, attr, value)
        yield
        setattr(obj, attr, orig)


def mock_source(name, **kwsrc):
    return models.Source.from_data(name, **kwsrc)
