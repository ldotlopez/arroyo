# -*- coding: utf-8 -*-
# vim: set fileencoding=utf-8 :

import unittest

import os

from appkit import network

import testapp
from arroyo.importer import OriginSpec


class ImporterTest(unittest.TestCase):
    def test_import_origin(self):
        app = testapp.TestApp({
            'plugin.eztv.enabled': True
        })

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
        self.assertTrue(isinstance(e, network.FetchError))

    def test_foo(self):
        app = testapp.TestApp()

        psrcs = [
            {'name': 'foo - 1x01', 'uri': 'http://example.com/name-1x01'},
            {'name': 'foo - 1x02', 'uri': 'http://example.com/name-1x02'},
            {'name': 'bar - 1x03',
             'urn': 'urn:btih:0000000000000000000000000000000000000001',
             'uri': 'magnet:?xt=urn:btih:0000000000000000000000000000000000000001&dn=bar.1x03'}
        ]

        # Fake normalize
        for (idx, x) in enumerate(psrcs):
            psrcs[idx]['provider'] = 'mock'
            psrcs[idx]['_discriminator'] = (
                psrcs[idx].get('urn', None) or
                psrcs[idx].get('uri', None)
            )
            psrcs[idx]['created'] = 0

        ret = app.importer._get_sources_for_data(*psrcs)
        self.assertTrue(
            all([set(ret[x]) == set(['created']) for x in ret])
        )
        for x in ret:
            app.db.session.add(x)
        app.db.session.commit()

        ret = app.importer._get_sources_for_data(psrcs[1])
        self.assertEqual(ret[psrcs[1]['name']], ['updated'])

if __name__ == '__main__':
    unittest.main()
