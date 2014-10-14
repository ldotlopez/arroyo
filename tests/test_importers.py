# -*- coding: utf-8 -*-
# [SublimeLinter pep8-max-line-length:119]
# vim: set fileencoding=utf-8 :

import unittest
import re

from path import path

from arroyo.importers import tpb, eztv, tpbrss, spanishtracker

IMPORTERS = [eztv, tpb, tpbrss, spanishtracker]


class TestGenerators(unittest.TestCase):
    def test_implementations(self):
        for mod in IMPORTERS:
            # General sanity checks
            self.assertTrue(hasattr(mod, 'url_generator'), msg='No url_generator() in {}'.format(mod))
            self.assertTrue(hasattr(mod, 'process'), msg='No process() in {}'.format(mod))
            self.assertTrue(hasattr(mod, 'BASE_URL'), msg='No BASE_URL in {}'.format(mod))

    def test_initial_seed(self):
        for mod in IMPORTERS:
            # Check if url_generator can be called without parameters
            g = mod.url_generator()
            self.assertEqual(next(g), mod.BASE_URL)

            # Check call with base_url
            g = mod.url_generator(mod.BASE_URL)
            self.assertEqual(next(g), mod.BASE_URL)

    def test_eztv(self):
        # General URLs
        g = eztv.url_generator()
        self.assertEqual(
            [next(g), next(g), next(g)],
            ['http://eztv.it/page_{}'.format(i) for i in [0, 1, 2]]
            )

        # Show-specific URLs only return one URL
        url = 'http://eztv.it/shows/123/show-title/'
        g = eztv.url_generator('http://eztv.it/shows/123/show-title/')
        self.assertEqual(next(g), url)

        with self.assertRaises(StopIteration):
            next(g)

        # Any other URL must fallback to general urls
        g = eztv.url_generator('http://eztv.it/non-existent-path/')
        self.assertEqual(next(g), eztv.BASE_URL)

    def test_tpb(self):
        # General URLs
        g = tpb.url_generator()
        self.assertEqual(
            [next(g), next(g), next(g)],
            ['http://thepiratebay.com/recent/{}/'.format(i) for i in [0, 1, 2]]
            )

        # Test pagination
        g = tpb.url_generator('http://thepiratebay.com/recent/8')
        self.assertEqual(next(g), 'http://thepiratebay.com/recent/8/')
        self.assertEqual(next(g), 'http://thepiratebay.com/recent/9/')

        g = tpb.url_generator('http://thepiratebay.com/a/8/b')
        self.assertEqual(next(g), 'http://thepiratebay.com/a/8/b/')
        self.assertEqual(next(g), 'http://thepiratebay.com/a/9/b/')

    def test_tpbrss(self):
        # Basic test
        g = tpbrss.url_generator()
        next(g)
        with self.assertRaises(StopIteration):
            next(g)

        url = 'http://example.com/foo/bar/'
        g = tpbrss.url_generator(url)
        self.assertEqual(next(g), url)

    def test_spanishtracker(self):
        st = spanishtracker

        # General URLs
        g = st.url_generator()
        self.assertEqual(
            [next(g), next(g), next(g)],
            ['http://spanishtracker.com/torrents.php?page={}'.format(i) for i in [0, 1, 2]]
            )

        # Respect parameters
        g = st.url_generator('http://spanishtracker.com/torrents.php?foo=bar&page=3&aaa=bbb')
        self.assertEqual(
            [next(g), next(g), next(g)],
            ['http://spanishtracker.com/torrents.php?aaa=bbb&foo=bar&page={}'.format(i) for i in [3, 4, 5]]
            )


class TestProcessors(unittest.TestCase):
    def test_implementations(self):
        for mod in IMPORTERS:
            # General sanity checks
            self.assertTrue(hasattr(mod, 'process'), msg='No process() in {}'.format(mod))

    def test_processing(self):
        eztv_keys = ['language', 'name', 'timestamp', 'type', 'uri']
        tpb_keys = ['leechers', 'name', 'seeds', 'size', 'timestamp', 'uri']
        tpbrss_keys = ['name', 'size', 'timestamp', 'uri']
        spanishtracker_keys = ['language', 'leechers', 'name', 'seeds', 'size', 'timestamp', 'type', 'uri']

        tests = (
            (eztv, 'eztv_main.html', 50, eztv_keys),
            (eztv, 'eztv_show.html', 84, eztv_keys),

            (tpb, 'tpb_main.html', 30, tpb_keys),
            (tpb, 'tpb_user.html', 30, tpb_keys),

            (tpbrss, 'tpbrss_main.html', 60, tpbrss_keys),

            (spanishtracker, 'spanishtracker_main.html', 30, spanishtracker_keys)
        )

        for (mod, sample, nelements, keys) in tests:
            sample = path(__file__).dirname() / "samples" / sample
            fh = open(sample)
            res = mod.process(fh.read())
            fh.close()

            self.assertEqual(len(res), nelements, msg="wrong processing on {}".format(sample))

            for r in res:
                language = r.get('language', None)
                if language:
                    self.assertIsNotNone(
                        re.match(r'^[a-z]{2}(-[a-z]{2,3})?$', language),
                        msg='Language {} invalid in {}'.format(language, mod))

                self.assertEqual(
                    sorted(r.keys()),
                    sorted(keys),
                    msg="Results from {} doesn't matches keys".format(mod))


if __name__ == '__main__':
    unittest.main()
