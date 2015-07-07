import contextlib
import os


from arroyo import core, models


class TestApp(core.Arroyo):
    def __init__(self, d={}):
        basedir = os.path.dirname(__file__)
        mock_fetcher_basedir = os.path.join(basedir, 'www-samples')

        settings = core.ArroyoStore(d)
        settings.set('auto-cron', False)
        settings.set('auto-import', False)
        settings.set('fetcher', 'mock')
        settings.set('fetcher.mock.basedir', mock_fetcher_basedir)
        settings.set('db-uri', 'sqlite:///:memory:')
        settings.set('downloader', 'mock')
        settings.set('log-format', '%(message)s')
        settings.set('log-level', 'WARNING')

        settings.set('extensions.downloaders.mock.enabled', True)

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

            if src.type:
                self.mediainfo.process(src)

            self.db.session.add(src)

        self.db.session.commit()

    @contextlib.contextmanager
    def hijack(self, obj, attr, value):
        orig = getattr(obj, attr)
        setattr(obj, attr, value)
        yield
        setattr(obj, attr, orig)


def mock_source(name, **kwsrc):
    return models.Source.from_data(name, **kwsrc)
