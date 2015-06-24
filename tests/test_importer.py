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
        self.settings = core.build_basic_settings()
        self.settings.set('mediainfo', False)
        self.settings.set('log-level', 'CRITICAL')
        self.settings.set('db-uri', 'sqlite:///:memory:')

    def set_mock_fetcher(self):
        basedir = os.path.dirname(__file__)
        mock_fetcher_basedir = os.path.join(basedir, 'www-samples')

        self.settings.delete('fetcher')
        self.settings.set('fetcher', 'mock')
        self.settings.set('fetcher.mock.basedir', mock_fetcher_basedir)

        return self.settings

    def test_import_get_origins(self):
        app = core.Arroyo(self.settings)
        app.importer.get_origins()

    def test_import_origin(self):
        self.set_mock_fetcher()
        app = core.Arroyo(self.settings)

        spec = OriginSpec(name='test', backend='eztv',
                          url='http://eztv.ch/page_0')

        # Check successful import
        ret = app.importer.import_origin_spec(spec)

        self.assertEqual(len(ret['added-sources']), 41)
        self.assertEqual(len(ret['updated-sources']), 0)

        # Check updating sources
        ret = app.importer.import_origin_spec(spec)

        self.assertEqual(len(ret['added-sources']), 0)
        self.assertEqual(len(ret['updated-sources']), 41)

        # Check for invalid URLs
        spec = OriginSpec(name='test', backend='eztv',
                          url='http://nowhere.com/invalid')
        ret = app.importer.import_origin_spec(spec)
        e = ret['errors']['http://nowhere.com/invalid']

        self.assertEqual(len(ret['added-sources']), 0)
        self.assertEqual(len(ret['updated-sources']), 0)
        self.assertTrue(isinstance(e, fetchers.FetchError))


if __name__ == '__main__':
    unittest.main()
