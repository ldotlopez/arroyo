# -*- coding: utf-8 -*-
# [SublimeLinter pep8-max-line-length:119]
# vim: set fileencoding=utf-8 :

import unittest

import os

from ldotcommons import fetchers

from arroyo import core
from arroyo.importer import OriginSpec


class ImporterTest(unittest.TestCase):
    def setUp(self):
        self.settings = \
            self.set_memory_db_uri(
                self.set_mock_fetcher(
                    self.disable_mediainfo(
                        self.disable_logging(
                            core.build_basic_settings()))))

    def disable_mediainfo(self, settings):
        settings.set('mediainfo', False)
        return settings

    def disable_logging(self, settings):
        settings.set('log-level', 'CRITICAL')
        return settings

    def set_memory_db_uri(self, settings):
        settings.set('db-uri', 'sqlite:///:memory:')
        return settings

    def set_mock_fetcher(self, settings):
        basedir = os.path.dirname(__file__)
        mock_fetcher_basedir = os.path.join(basedir, 'www-samples')

        settings.delete('fetcher')
        settings.set('fetcher', 'mock')
        settings.set('fetcher.mock.basedir', mock_fetcher_basedir)

        return settings

    def test_import_origin(self):
        app = core.Arroyo(self.settings)

        spec = OriginSpec(name='test', backend='eztv',
                          url='http://eztv.ch/page_0')

        # Check successful import
        ret = app.importer.import_origin(spec)

        self.assertEqual(len(ret['added-sources']), 41)
        self.assertEqual(len(ret['updated-sources']), 0)

        # Check updating sources
        ret = app.importer.import_origin(spec)

        self.assertEqual(len(ret['added-sources']), 0)
        self.assertEqual(len(ret['updated-sources']), 41)

        # Check for invalid URLs
        spec = OriginSpec(name='test', backend='eztv',
                          url='http://nowhere.com/invalid')
        ret = app.importer.import_origin(spec)
        e = ret['errors']['http://nowhere.com/invalid']

        self.assertEqual(len(ret['added-sources']), 0)
        self.assertEqual(len(ret['updated-sources']), 0)
        self.assertTrue(isinstance(e, fetchers.FetchError))

if __name__ == '__main__':
    unittest.main()
