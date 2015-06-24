import unittest

import os

from arroyo import core, importer


class BaseTest:
    def setUp(self):
        basedir = os.path.dirname(__file__)
        mock_fetcher_basedir = os.path.join(basedir, 'www-samples')

        settings = core.build_basic_settings()
        settings.delete('fetcher')
        settings.set('fetcher', 'mock')
        settings.set('fetcher.mock.basedir', mock_fetcher_basedir)
        settings.set('db-uri', 'sqlite:///:memory:')

        self.app = core.Arroyo(settings)

    def _test_process(self, backend, url, n_sources_expected):
        spec = importer.OriginSpec(name='test', backend=backend, url=url)
        origin = self.app.importer.get_origin_for_origin_spec(spec)

        url_ = next(origin.get_urls())
        self.assertEqual(url, url_)

        buff = self.app.fetcher.fetch(url)
        srcs = origin.process(buff)
        self.assertEqual(len(srcs), n_sources_expected)


class TpbTest(BaseTest, unittest.TestCase):
    def test_process_recent_page(self):
        self._test_process(
            'tpb', 'https://thepiratebay.am/recent', 30)

    def test_process_search_page(self):
        self._test_process(
            'tpb', 'https://thepiratebay.am/search/a/0/99/0', 30)

if __name__ == '__main__':
    unittest.main()
