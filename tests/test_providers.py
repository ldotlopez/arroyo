# -*- coding: utf-8 -*-

import unittest
import warnings

from arroyo import pluginlib
import testapp


warnings.warn("This test doesn't validate keys")


class TestProvider:
    PARSE_TESTS = []
    PAGINATION_TESTS = []
    QUERY_TESTS = []

    def setUp(self):
        settings = {
            'plugins.queries.source.enabled': True,
            'plugins.queries.episode.enabled': True,
            'plugins.queries.movie.enabled': True
        }
        settings.update(
            {'plugins.' + x + '.enabled': True
             for x in self.PLUGINS}
        )
        self.app = testapp.TestApp(settings)

    def test_implementation(self):
        impl = self.app.get_extension(
            pluginlib.Provider,
            self.PROVIDER_NAME)

        self.assertTrue(
            hasattr(impl, 'paginate'),
            msg='No paginate() in {}'.format(impl))
        self.assertTrue(
            hasattr(impl, 'parse'),
            msg='No process() in {}'.format(impl))
        self.assertTrue(
            hasattr(impl, 'DEFAULT_URI'),
            msg='No DEFAULT_URI in {}'.format(impl))

    def test_pagination(self):
        for (start, expected) in self.PAGINATION_TESTS:
            provider = self.app.get_extension(pluginlib.Provider,
                                              self.PROVIDER_NAME)
            g = provider.paginate(start or provider.DEFAULT_URI)
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
            provider = self.app.get_extension(
                pluginlib.Provider,
                self.PROVIDER_NAME)

            with open(testapp.www_sample_path(sample), 'rb') as fh:
                results = list(provider.parse(fh.read()))

            self.assertEqual(
                n_expected, len(results),
                msg="Parse missmatch for {}".format(sample)
            )

    def test_query_uri(self):
        provider = self.app.get_extension(
            pluginlib.Provider, self.PROVIDER_NAME
        )

        for (query, uri) in self.QUERY_TESTS:
            if not isinstance(query, dict):
                words = [x for x in query.split(' ') if x]
                query = {'name-glob': '*' + '*'.join(words) + '*'}

            query = self.app.selector.query_from_params(query)

            self.assertEqual(
                uri,
                provider.get_query_uri(query),
                msg='Failed query for {}'.format(repr(query)))


class ElitetorrentTest(TestProvider, unittest.TestCase):
    PLUGINS = ['providers.elitetorrent']
    PROVIDER_NAME = 'elitetorrent'

    PAGINATION_TESTS = [
        # (baseuri, [page_n, page_n+1, ...])
    ]

    PARSE_TESTS = [
        ('elitetorrent-listing.html', 48),
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
            'http://www.elitetorrent.net/resultados/new+girl/orden:fecha',
        ),
    ]


class EztvTest(TestProvider, unittest.TestCase):
    PLUGINS = ['providers.eztv']
    PROVIDER_NAME = 'eztv'

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
        ('eztv-bsg.html', 96),
    ]

    QUERY_TESTS = [
        ('foo', None),
        (dict(kind='episode', series='lost'), 'https://eztv.ag/search/lost'),  # nopep8
        (dict(kind='episode', series='youre the worst'), 'https://eztv.ag/search/youre-the-worst')  # nopep8
    ]


class KickassTest(TestProvider, unittest.TestCase):
    PLUGINS = ['providers.kickass']
    PROVIDER_NAME = 'kickass'

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

        ('https://kickass.cd/usearch/the+walking+dead/', [
            'https://kickass.cd/usearch/the+walking+dead/',
            'https://kickass.cd/usearch/the+walking+dead/2/'
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
        ('kat-avs-search.html', 30),
        ('kat-full.html', 120)
    ]

    QUERY_TESTS = [
        (
            'the big bang theory',
            'https://kickass.cd/usearch/the+big+bang+theory/?field=time_add&sorder=desc'  # nopep8
        ),
        (
            dict(kind='episode', series='the big bang theory'),
            'https://kickass.cd/usearch/the+big+bang+theory+category%3Atv/?field=time_add&sorder=desc'  # nopep8
        )
    ]


class NyaaTest(TestProvider, unittest.TestCase):
    PLUGINS = ['providers.nyaa']
    PROVIDER_NAME = 'nyaa'

    PAGINATION_TESTS = [
        (None, [
            'https://www.nyaa.se/?sort=0&order=1',
            'https://www.nyaa.se/?sort=0&order=1&offset=2']),
    ]

    PARSE_TESTS = [
        ('nyaa-listing.html', 105),
        ('nyaa-detail.html', 1)
    ]


class ThepiratebayTest(TestProvider, unittest.TestCase):
    PLUGINS = ['providers.thepiratebay']
    PROVIDER_NAME = 'thepiratebay'

    PAGINATION_TESTS = [
        # Basic
        (None, [
            'https://thepiratebay.cr/recent/0/',
            'https://thepiratebay.cr/recent/1/',
            'https://thepiratebay.cr/recent/2/'
        ]),

        # Simple search
        (r'https://thepiratebay.cr/search/the%20americans/0/7/', [
            r'https://thepiratebay.cr/search/the%20americans/0/7/',
            r'https://thepiratebay.cr/search/the%20americans/1/7/',
            r'https://thepiratebay.cr/search/the%20americans/2/7/'
        ]),

        # Category pagination
        ('https://thepiratebay.cr/browse/605/', [
                'https://thepiratebay.cr/browse/605/',
                'https://thepiratebay.cr/browse/605/1/3',
                'https://thepiratebay.cr/browse/605/2/3',
        ])
    ]


class TorrentAPITest(TestProvider, unittest.TestCase):
    PLUGINS = ['providers.torrentapi']
    PROVIDER_NAME = 'torrentapi'

    PAGINATION_TESTS = [
    ]

    PARSE_TESTS = [
        ('torrentapi-listing.json', 25)
    ]

    QUERY_TESTS = [
    ]


class YtsTest(TestProvider, unittest.TestCase):
    PLUGINS = ['providers.yts']
    PROVIDER_NAME = 'yts'

    PAGINATION_TESTS = [
    ]

    PARSE_TESTS = [
        ('yts-listing.html', 40),
        ('yts-detail.html', 2)
    ]

    QUERY_TESTS = [
    ]


if __name__ == '__main__':
    unittest.main()
