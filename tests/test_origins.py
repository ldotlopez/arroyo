# -*- coding: utf-8 -*-

import unittest
import warnings

from arroyo import plugin
import testapp


warnings.warn("This test doesn't validate keys")


class TestOrigin:
    PARSE_TESTS = []
    PAGINATION_TESTS = []
    QUERY_TESTS = []

    def setUp(self):
        settings = {
            'plugin.sourcequery.enabled': True,
            'plugin.episodequery.enabled': True,
            'plugin.moviequery.enabled': True
        }
        settings.update(
            {'plugin.' + x + '.enabled': True
             for x in self.PLUGINS}
        )
        self.app = testapp.TestApp(settings)

    def test_implementation(self):
        impl = self.app.get_implementation(
            plugin.Origin,
            self.IMPLEMENTATION_NAME)

        self.assertTrue(
            hasattr(impl, 'paginate'),
            msg='No paginate() in {}'.format(impl))
        self.assertTrue(
            hasattr(impl, 'process'),
            msg='No process() in {}'.format(impl))
        self.assertTrue(
            hasattr(impl, 'DEFAULT_URI'),
            msg='No DEFAULT_URI in {}'.format(impl))

    def test_pagination(self):
        for (start, expected) in self.PAGINATION_TESTS:
            origin = self.app.get_extension(
                plugin.Origin,
                self.IMPLEMENTATION_NAME,
                uri=start)

            g = origin.paginate()
            collected = []

            while len(collected) < len(expected):
                try:
                    collected.append(next(g))
                except StopIteration:
                    collected.append(None)

            self.assertEqual(collected, expected,
                             msg='Fail pagination for {}'.format(start))

    def test_parse(self):
        for (sample, n_expected) in self.PARSE_TESTS:
            origin = self.app.get_extension(
                plugin.Origin,
                self.IMPLEMENTATION_NAME)

            with open(testapp.www_sample_path(sample), 'rb') as fh:
                results = list(origin.parse(fh.read()))

            self.assertEqual(
                n_expected, len(results),
                msg="Parse missmatch for {}".format(sample)
            )

    def test_query_uri(self):
        origin = self.app.get_extension(
            plugin.Origin, self.IMPLEMENTATION_NAME
        )

        for (query, uri) in self.QUERY_TESTS:
            if not isinstance(query, dict):
                words = [x for x in query.split(' ') if x]
                query = {'name-glob': '*' + '*'.join(words) + '*'}

            query = self.app.selector.get_query_from_params(query)

            self.assertEqual(
                uri,
                origin.get_query_uri(query),
                msg='Failed query for {}'.format(repr(query)))


class EztvTest(TestOrigin, unittest.TestCase):
    PLUGINS = ['eztv']
    IMPLEMENTATION_NAME = 'eztv'

    PAGINATION_TESTS = [
        # (baseuri, [page_n, page_n+1, ...])

        (None, [
            'https://eztv.ag/page_0'
        ]),

        ('https://eztv.ag/page_0', [
            'https://eztv.ag/page_0',
            'https://eztv.ag/page_1',
            'https://eztv.ag/page_2'
        ]),

        ('https://eztv.ag/page_19', [
            'https://eztv.ag/page_19',
            'https://eztv.ag/page_20'
        ]),

        # ('https://eztv.ag/foo', None),  # Not sure how to handle this
    ]

    PARSE_TESTS = [
        ('eztv-page-0.html', 50),
        ('eztv-hcf.html', 50),
    ]

    QUERY_TESTS = [
        ('foo', None),
        (dict(kind='episode', series='lost'), 'https://eztv.ag/search/lost'),  # nopep8
        (dict(kind='episode', series='youre the worst'), 'https://eztv.ag/search/youre-the-worst')  # nopep8
    ]

    # def test_series_index_parse(self):
    #     eztv = self.app.get_extension(
    #         plugin.Origin,
    #         self.IMPLEMENTATION_NAME
    #     )
    #     with open(testapp.www_sample_path('eztv-series-index.html')) as fh:
    #         res = eztv.parse_series_index(fh.read())

    #     self.assertEqual(
    #         res['The Walking Dead'],
    #         'https://eztv.ag/shows/428/the-walking-dead/'
    #     )
    #     self.assertEqual(len(res), 1830)

    # def test_series_table_selector(self):
    #     eztv = self.app.get_extension(
    #         plugin.Origin,
    #         self.IMPLEMENTATION_NAME
    #     )

    #     with open(testapp.www_sample_path('eztv-series-index.html')) as fh:
    #         table = eztv.parse_series_index(fh.read())

    #     self.assertEqual(
    #         eztv.get_url_for_series(table, 'Battlestar Galactica'),
    #         'https://eztv.ag/shows/18/battlestar-galactica/'
    #     )

    #     self.assertEqual(
    #         eztv.get_url_for_series(table, 'battlestar galactica'),
    #         'https://eztv.ag/shows/18/battlestar-galactica/'
    #     )

    #     self.assertEqual(
    #         eztv.get_url_for_series(table, 'the leftovers'),
    #         'https://eztv.ag/shows/1060/the-leftovers/'
    #     )

    #     with self.assertRaises(KeyError):
    #         eztv.get_url_for_series(table, 'foo')


class KickassTest(TestOrigin, unittest.TestCase):
    PLUGINS = ['kickass']
    IMPLEMENTATION_NAME = 'kickass'

    PAGINATION_TESTS = [
        # (baseuri, [page_n, page_n+1, ...])

        (None, [
            'https://kickass.cd/new/',
            'https://kickass.cd/new/2/'
        ]),

        ('https://kickass.cd/new/15/', [
            'https://kickass.cd/new/15/',
            'https://kickass.cd/new/16/',
            'https://kickass.cd/new/17/'
        ]),

        ('https://kickass.cd/usearch/the%20walking%20dead/', [
            'https://kickass.cd/usearch/the%20walking%20dead/',
            'https://kickass.cd/usearch/the%20walking%20dead/2/'
        ]),

        ('https://kickass.cd/tv/?field=size&sorder=desc', [
            'https://kickass.cd/tv/?field=size&sorder=desc',
            'https://kickass.cd/tv/2/?field=size&sorder=desc',
            'https://kickass.cd/tv/3/?field=size&sorder=desc'
        ]),

        ('https://kickass.cd/usearch/lost/?field=time_add&sorder=desc', [
            'https://kickass.cd/usearch/lost/?field=time_add&sorder=desc',
            'https://kickass.cd/usearch/lost/2/?field=time_add&sorder=desc'
        ]),

        ('https://kickass.cd/no-final-slash', [
            'https://kickass.cd/no-final-slash/',
            'https://kickass.cd/no-final-slash/2/',
        ]),

        # ('https://eztv.ag/foo', None),  # Not sure how to handle this
    ]

    PARSE_TESTS = [
        ('kat-new.html', 30),
        ('kat-tv.html', 30),
        ('kat-full.html', 120)
    ]

    QUERY_TESTS = [
        (
            'the big bang theory',
            'https://kickass.cd/usearch/the%20big%20bang%20theory/?field=time_add&sorder=desc'  # nopep8
        ),
        (
            dict(kind='episode', series='the big bang theory'),
            'https://kickass.cd/usearch/the%20big%20bang%20theory%20category%3Atv/?field=time_add&sorder=desc'  # nopep8
        )
    ]


class ElitetorrentTest(TestOrigin, unittest.TestCase):
    PLUGINS = ['elitetorrent']
    IMPLEMENTATION_NAME = 'elitetorrent'

    PAGINATION_TESTS = [
        # (baseuri, [page_n, page_n+1, ...])
    ]

    PARSE_TESTS = [
        ('elitetorrent-listing.html', 42),
        ('elitetorrent-search-result.html', 48),
        ('elitetorrent-detail.html', 1),
    ]

    QUERY_TESTS = [
        (
            'new girl',  # language=esp-es required
            None,
        ),
        (
            dict(name='new girl', language='spa-es'),
            'http://www.elitetorrent.net/busqueda/new+girl',
        ),
    ]


if __name__ == '__main__':
    unittest.main()
