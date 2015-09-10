# -*- coding: utf-8 -*-
# [SublimeLinter pep8-max-line-length:119]
# vim: set fileencoding=utf-8 :

import unittest

import os

from ldotcommons import fetchers

import testapp
from arroyo.importer import OriginSpec


class ImporterTest(unittest.TestCase):
    def setUp(self):
        settings = {}

        basedir = os.path.dirname(__file__)
        basedir = os.path.join(basedir, 'www-samples')

        settings = {
            'fetcher': 'mock',
            'fetcher.mock.basedir': basedir,
            'plugin.eztv.enabled': True
        }

        self.app = testapp.TestApp(settings)

    def test_import_origin(self):
        spec = OriginSpec(name='test', backend='eztv',
                          url='http://eztv.ch/page_0')

        # Check successful import
        ret = self.app.importer.import_origin_spec(spec)

        self.assertEqual(len(ret['added-sources']), 41)
        self.assertEqual(len(ret['updated-sources']), 0)

        # Check updating sources
        ret = self.app.importer.import_origin_spec(spec)

        self.assertEqual(len(ret['added-sources']), 0)
        self.assertEqual(len(ret['updated-sources']), 41)

        # Check for invalid URLs
        spec = OriginSpec(name='test', backend='eztv',
                          url='http://nowhere.com/invalid')
        ret = self.app.importer.import_origin_spec(spec)
        e = ret['errors']['http://nowhere.com/invalid']

        self.assertEqual(len(ret['added-sources']), 0)
        self.assertEqual(len(ret['updated-sources']), 0)
        self.assertTrue(isinstance(e, fetchers.FetchError))


if __name__ == '__main__':
    unittest.main()
