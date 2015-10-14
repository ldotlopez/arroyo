# -*- coding: utf-8 -*-

import unittest
import warnings

from arroyo import plugin
import testapp


class TestOrigin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        warnings.warn("TestOrigin doesn't validate keys")

    def setUp(self):
        settings = {}
        settings.update(
            {'plugin.' + x + '.enabled': True
             for x in self.PLUGINS}
        )
        self.app = testapp.TestApp(settings)

    def test_implementation(self):
        impl = self.app.get_implementation(plugin.Origin, self.BACKEND)
        self.assertTrue(
            hasattr(impl, 'paginate'),
            msg='No paginate() in {}'.format(impl))
        self.assertTrue(
            hasattr(impl, 'process'),
            msg='No process() in {}'.format(impl))
        self.assertTrue(
            hasattr(impl, 'BASE_URL'),
            msg='No BASE_URL in {}'.format(impl))

    def test_initial_seed(self):
        spec = plugin.OriginSpec(name='foo', backend=self.BACKEND)
        origin = self.app.importer.get_origin_for_origin_spec(spec)

        g = origin.paginate(origin.BASE_URL)
        self.assertEqual(next(g), origin.BASE_URL)

    def test_pagination(self):
        spec = plugin.OriginSpec(name='foo', backend=self.BACKEND)
        origin = self.app.importer.get_origin_for_origin_spec(spec)

        for (start, expected) in self.PAGINATIONS.items():
            start = start or origin.BASE_URL
            g = origin.paginate(start)
            collected = []

            while len(collected) < len(expected):
                try:
                    collected.append(next(g))
                except StopIteration:
                    collected.append(None)

            self.assertEqual(collected, expected)

    def test_processors(self):
        for (url, n_expected) in self.URL_TESTS:
            spec = plugin.OriginSpec(
                name='foo', backend=self.BACKEND, url=url)

            srcs = self.app.importer.import_origin_spec(spec)
            srcs = srcs['added-sources'] + srcs['updated-sources']
            self.assertEqual(
                len(srcs), n_expected,
                msg='From {}'.format(url))


class TestEztv(TestOrigin, unittest.TestCase):
    PLUGINS = ['eztv']
    BACKEND = 'eztv'
    KEYS = ['language', 'name', 'timestamp', 'type', 'uri']
    PAGINATIONS = {
        # Default
        None: ['https://eztv.ch/page_{}'.format(i) for i in [0, 1, 2]],

        # TV Show page
        'http://eztv.it/shows/123/show-title/':
            ['http://eztv.it/shows/123/show-title/', None],

        # TDL change and start at page 3
        'https://eztv.xx/page_2':
            ['https://eztv.xx/page_{}'.format(i) for i in [2, 3]]

    }
    URL_TESTS = [
        ('http://eztv.ch/page/0', 41)
    ]


class TestKickass(TestOrigin, unittest.TestCase):
    PLUGINS = ['kickass']
    BACKEND = 'kickass'
    KEYS = []
    PAGINATIONS = {
        # Default
        None: ['http://kat.cr/new/?page=1'],

        # Index at 7
        'http://kat.cr/usearch?foo=bar&page=8&lol=wow':
            ['http://kat.cr/usearch?foo=bar&page={}&lol=wow'.format(i)
             for i in range(8, 17)],

        'http://kat.cr/usearch/category%3Atv%200sec/?page=1':
            ['http://kat.cr/usearch/category%3Atv%200sec/?page={}'.format(i)
             for i in range(1, 5)]
    }
    URL_TESTS = [
        (r'http://kat.cr/usearch/category%3Atv%200sec/', 25)
    ]


class TestSpanishTracker(TestOrigin, unittest.TestCase):
    PLUGINS = ['spanishtracker']
    BACKEND = 'spanishtracker'
    KEYS = [
        'language', 'leechers', 'name', 'seeds', 'size', 'timestamp',
        'type', 'uri'
    ]
    PAGINATIONS = {
        'http://spanishtracker.com/torrents.php?aaa=bbb&foo=bar&page=3':
            ['http://spanishtracker.com/torrents.php?aaa=bbb&foo=bar&page={}'.format(i)
             for i in [3, 4, 5]]
    }
    URL_TESTS = []


class TestTpb(TestOrigin, unittest.TestCase):
    PLUGINS = ['thepiratebay']
    BACKEND = 'tpb'
    KEYS = ['leechers', 'name', 'seeds', 'size', 'timestamp', 'uri']
    PAGINATIONS = {
        'http://thepiratebay.com/recent/0/':
            ['http://thepiratebay.com/recent/{}/'.format(i)
             for i in range(2)],

        'http://thepiratebay.com/recent/45/':
            ['http://thepiratebay.com/recent/{}/'.format(i)
             for i in [45, 46]],

        'http://thepiratebay.com/recent/8/b/':
            ['http://thepiratebay.com/recent/{}/b/'.format(i)
             for i in [8, 9]]
    }
    URL_TESTS = [
        ('https://thepiratebay.am/recent', 30),
        ('https://thepiratebay.am/search/a/0/99/0', 30)
    ]


class TestTpbRss(TestOrigin, unittest.TestCase):
    PLUGINS = ['thepiratebay']
    BACKEND = 'tpbrss'
    KEYS = ['name', 'size', 'timestamp', 'uri']
    PAGINATIONS = {}
    URL_TESTS = []


#     def test_processing(self):

#         tests = (
#             (eztv, 'eztv_main.html', 50, eztv_keys),
#             (eztv, 'eztv_show.html', 84, eztv_keys),

#             (tpb, 'tpb_main.html', 30, tpb_keys),
#             (tpb, 'tpb_user.html', 30, tpb_keys),

#             (tpbrss, 'tpbrss_main.html', 60, tpbrss_keys),

#             (spanishtracker, 'spanishtracker_main.html', 30,
#              spanishtracker_keys)
#         )

#         for (mod, sample, nelements, keys) in tests:
#             sample = path(__file__).dirname() / "samples" / sample
#             fh = open(sample)
#             res = mod.process(fh.read())
#             fh.close()

#             self.assertEqual(len(res), nelements,
#                              msg="wrong processing on {}".format(sample))

#             for r in res:
#                 language = r.get('language', None)
#                 if language:
#                     self.assertIsNotNone(
#                         re.match(r'^[a-z]{2}(-[a-z]{2,3})?$', language),
#                         msg='Language {} invalid in {}'.format(language, mod))

#                 self.assertEqual(
#                     sorted(r.keys()),
#                     sorted(keys),
#                     msg="Results from {} doesn't matches keys".format(mod))


if __name__ == '__main__':
    unittest.main()
