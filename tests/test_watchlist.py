# -*- coding: utf-8 -*-
# [SublimeLinter pep8-max-line-length:119]
# vim: set fileencoding=utf-8 :

import unittest

from arroyo import plugin
from arroyo.plugins import watchlist
import testapp


class WatchlistTest(unittest.TestCase):
    def setUp(self):
        conf = {
            # 'plugin.watchlist.enable': True
        }
        self.app = testapp.TestApp(conf)

    def test_scan(self):
        w = watchlist.Watchlist(self.app)

        with open(testapp.www_sample_path('imdb-user-watchlist.html')) as fh:
            w.parse(fh.read())

        pass

if __name__ == '__main__':
    unittest.main()
