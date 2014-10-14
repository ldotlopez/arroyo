# -*- coding: utf-8 -*-
# [SublimeLinter pep8-max-line-length:119]
# vim: set fileencoding=utf-8 :

import unittest

import importlib

from path import path

from ldotcommons import fetchers
from ldotcommons import sqlalchemy as ldotsa

from arroyo import analize, filtering, db
from arroyo.downloaders import mock
from arroyo.tests import common

SAMPLES = (
    ('tpb', 'http://thepiratebay.se/user/eztv', 30),
    ('spanishtracker', 'http://spanishtracker.com/torrents.php?search=&category=1&active=1', 30),
    ('eztv', 'http://eztv.it/shows/36/breaking-bad/', 83),  # Really 84, but has one duplicate
)


class TestE2EAnalize(unittest.TestCase):
    def test_pipeline(self):
        for (anlz, url, nelements) in SAMPLES:
            analizer_mod = importlib.import_module('arroyo.importers.'+anlz)
            conn = ldotsa.create_session('sqlite:///:memory:')

            pipe = analize.build_pipeline(
                url_generator=analizer_mod.url_generator(url),
                iterations=1,
                fetcher_obj=fetchers.MockFetcher(basedir=path(__file__).dirname() / 'samples'),
                process_func=analizer_mod.process,
                overrides={'provider': anlz},
                db=conn)
            pipe.execute()

            self.assertEqual(
                ldotsa.query_from_params(conn, db.Source, provider=anlz).count(),
                nelements)

    def test_multiple(self):
        conn = ldotsa.create_session('sqlite:///:memory:')

        for (anlz, url, nelements) in SAMPLES:
            analizer_mod = importlib.import_module('arroyo.importers.'+anlz)
            pipe = analize.build_pipeline(
                url_generator=analizer_mod.url_generator(url),
                iterations=1,
                fetcher_obj=fetchers.MockFetcher(basedir=path(__file__).dirname() / 'samples'),
                process_func=analizer_mod.process,
                overrides={'provider': anlz},
                db=conn)
            pipe.execute()

        self.assertEqual(
            conn.query(db.Source).count(),
            sum([x[2] for x in SAMPLES]))


class TestE2EFiltering(unittest.TestCase):
    def setUp(self):
        self.conn = common.setup_session()

    def _pipeline_process(self, **filters):
        pipe = filtering.filtering_build_pipeline(
            self.conn,
            filters,
            mock.Downloader(session=self.conn))
        pipe.execute()

        return pipe.get('downloader').stats

    def test_filtering(self):
        stats = self._pipeline_process(name_regexp=r'title (a|b|c|d)')
        self.assertEqual(len(stats['added']), 4)
        self.assertEqual(len(stats['failed']), 0)

    def test_filtering_complex(self):
        stats = self._pipeline_process(name_regexp=r'title (a|b|c|d)', type='tvshow')
        self.assertEqual(len(stats['added']), 1)
        self.assertEqual(len(stats['failed']), 0)


if __name__ == '__main__':
    unittest.main()
