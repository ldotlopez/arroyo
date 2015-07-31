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

        # url_ = next(origin.get_urls())
        # self.assertEqual(url, url_)

        buff = self.app.fetcher.fetch(url)
        srcs = origin.process(buff)
        self.assertEqual(len(srcs), n_sources_expected)

    def _test_get_urls(self, backend, seed_url, urls):
        spec = importer.OriginSpec(
            name='test', backend=backend, url=seed_url, iterations=len(urls))
        origin = self.app.importer.get_origin_for_origin_spec(spec)

        generated = []

        g = origin.get_urls()
        for idx in range(len(urls)):
            try:
                generated.append(next(g))
            except StopIteration:
                break

        self.assertEqual(urls, generated)


class EztvTest(BaseTest, unittest.TestCase):
    def test_process_recent_page(self):
        self._test_process(
            'eztv', 'http://eztv.ch/page_0', 41)

    def test_get_urls(self):
        self._test_get_urls(
            'eztv',
            'http://eztv.ch/page_0',
            ['http://eztv.ch/page_0',
             'http://eztv.ch/page_1'])

    def test_get_urls_from_none(self):
        self._test_get_urls(
            'eztv',
            None,
            ['https://eztv.ch/page_0',
             'https://eztv.ch/page_1'])

    def test_get_urls_from_n(self):
        self._test_get_urls(
            'eztv',
            'http://eztv.ch/page_3',
            ['http://eztv.ch/page_3',
             'http://eztv.ch/page_4'])

    def test_get_urls_without_page(self):
        self._test_get_urls(
            'eztv',
            'http://eztv.ch/',
            ['http://eztv.ch/page_0',
             'http://eztv.ch/page_1'])


class TpbTest(BaseTest, unittest.TestCase):
    def test_process_recent_page(self):
        self._test_process(
            'tpb', 'https://thepiratebay.am/recent', 30)

    def test_process_search_page(self):
        self._test_process(
            'tpb', 'https://thepiratebay.am/search/a/0/99/0', 30)

    def test_get_urls(self):
        self._test_get_urls(
            'tpb',
            'https://thepiratebay.am/recent',
            ['https://thepiratebay.am/recent'])


class KickassTest(BaseTest, unittest.TestCase):
    def test_process(self):
        self._test_process(
            'kickass', 'http://kat.cr/usearch/category%3Atv%200sec/', 25)

    def test_get_urls(self):
        pass

if __name__ == '__main__':
    unittest.main()
