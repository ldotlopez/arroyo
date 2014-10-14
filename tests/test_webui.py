# -*- coding: utf-8 -*-
# [SublimeLinter pep8-max-line-length:119]
# vim: set fileencoding=utf-8 :

import unittest
import json

from arroyo import db
from arroyo.downloaders import mock
from arroyo.tests import common
from arroyo.webui import WebUI


def parse(response):
    return (json.loads(response.data.decode(response.charset)), response.status_code)


class TestApi(unittest.TestCase):
    def setUp(self):
        self.sess = common.setup_session()
        self.app = WebUI(session=self.sess, downloader=mock.Downloader(session=self.sess))

    def tearDown(self):
        self.app = None

    def test_type_validation(self):
        self.assertTrue(WebUI.is_safe_type('tvshow'))
        self.assertTrue(WebUI.is_safe_type('movie-dvdrip'))
        self.assertFalse(WebUI.is_safe_type('-dvdrip'))
        self.assertFalse(WebUI.is_safe_type('aÑa'))

    def test_language_validation(self):
        self.assertTrue(WebUI.is_safe_language('es'))
        self.assertTrue(WebUI.is_safe_language('es-es'))
        self.assertTrue(WebUI.is_safe_language('es-lat'))
        self.assertFalse(WebUI.is_safe_language('es_lat'))
        self.assertFalse(WebUI.is_safe_language('-es'))

    def test_vague_search(self):
        with self.app.test_client() as client:
            resp, code = parse(client.get('/search/?q=x'))
            self.assertEqual(code, 400)

    def test_simple_search(self):
        with self.app.test_client() as client:
            resp, code = parse(client.get('/search/?q=complex.title'))
            self.assertEqual(code, 200)
            self.assertEqual(len(resp), 2)

    def test_complex_search(self):
        with self.app.test_client() as client:
            resp, code = parse(client.get('/search/?q=...&type=tvshow&type=movie-dvdrip'))
            self.assertEqual(code, 200, msg=resp)
            self.assertEqual(len(resp), 2)

    def test_empty_list(self):
        with self.app.test_client() as client:
            resp, code = parse(client.get('/downloads/'))
            self.assertEqual(code, 200)
            self.assertEqual(resp, [])

    def test_add_download(self):
        with self.app.test_client() as client:
            resp, code = parse(client.get('/search/?q=...&type=tvshow&type=movie-dvdrip'))
            self.assertEqual(code, 200, msg=resp)
            self.assertEqual(len(resp), 2, msg=resp)

            ids = [x['id'] for x in resp]
            for source in self.sess.query(db.Source).filter(db.Source.id.in_(ids)):
                resp, code = parse(client.post('/downloads/', data={'id': source.id}))
                self.assertEqual(code, 200)
                self.assertEqual(resp['id'], source.id)

            resp, code = parse(client.get('/downloads/'))
            self.assertEqual(code, 200)
            self.assertEqual(
                sorted(ids),
                sorted(x['id'] for x in resp))

    def test_remove_download(self):
        with self.app.test_client() as client:
            sources = self.sess.query(db.Source).all()

            evens, odds = [[], []]
            i = 0
            for source in sources:
                resp, code = parse(client.post('/downloads/', data={'id': source.id}))
                self.assertEqual(code, 200)
                self.assertEqual(resp['id'], source.id)
                (odds if i % 2 else evens).append(source)

            for source in evens:
                resp, code = parse(client.delete('/downloads/{}'.format(source.id)))
                self.assertEqual(code, 200)

            resp, code = parse(client.get('/downloads/'))
            self.assertEqual(code, 200)
            self.assertEqual(
                sorted(x['id'] for x in resp),
                sorted(x.id for x in odds))

    def test_detail(self):
        with self.app.test_client() as client:
            source = self.sess.query(db.Source)[0]
            resp, code = parse(client.post('/downloads/', data={'id': source.id}))
            resp, code = parse(client.get('/downloads/{}'.format(source.id)))
            self.assertEqual(resp['name'], source.name)

if __name__ == '__main__':
    unittest.main()
