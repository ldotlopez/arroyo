# -*- coding: utf-8 -*-

import unittest


from arroyo import plugin
from arroyo.plugins import watchlist


import testapp


class WatchlistTest(unittest.TestCase):
    def setUp(self):
        self.app = testapp.TestApp({
            'plugin.watchlist.list.imdb': ''
        })

    def tearDown(self):
        delattr(self, 'app')

    def test_config(self):
        s1 = {
            'enabled': True,
            'label1': 'http://foo.com/',
            'label2': {
                'url': 'http://bar.com/',
                'locale': 'es_ES'
            }
        }
        self.app.settings.set('plugin.watchlist', s1)

    def test_parse(self):
        w = watchlist.Watchlist(self.app)
        with open(testapp.www_sample_path('imdb-user-watchlist.html')) as fh:
            res = w.parse(fh.read())
            self.assertEqual(
                len(res),
                92
            )

if __name__ == '__main__':
    unittest.main()
