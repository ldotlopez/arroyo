# -*- coding: utf-8 -*-
# [SublimeLinter pep8-max-line-length:119]
# vim: set fileencoding=utf-8 :

import unittest

from ldotcommons import sqlalchemy as ldotsa

from arroyo import db
from arroyo.tests import common

NAMES = [
    'This movie is a movie-dvdrip',
    'another movie-hdrip',
    'sample movie-hdrip',
    'simple and well know name',
    'the big one',
    'the little one',
    'this is a complex title with more than one match',
    'this is the second complex-title',
    'title A',
    'title B',
    'title C',
    'title D']


class TestFixtures(unittest.TestCase):
    def test_generation(self):
        data = db.source_data_builder(name='test 1')
        self.assertEqual(data['name'], 'test 1')
        self.assertIsNotNone(data['provider'])
        self.assertTrue(data['timestamp'] > 0)

        data = db.source_data_builder(name='test 1', provider='foo')
        self.assertEqual(data['provider'], 'foo')


class TestFilters(unittest.TestCase):
    def setUp(self):
        self.conn = common.setup_session()

    def _check_equal(self, filters, expected):
        res = ldotsa.query_from_params(self.conn, db.Source, **filters).all()
        self.assertEqual(
            sorted([x.name for x in res]),
            sorted(expected)
            )

    def test_by_name(self):
        self._check_equal(
            {'name': 'simple and well know name'},
            ['simple and well know name'])

    def test_by_name_fail(self):
        self._check_equal(
            {'name': 'I can\'t exist'},
            [])

    def test_by_name_complex(self):
        self._check_equal(
            {'name_like': '%complex_title%'},
            ['this is a complex title with more than one match',
             'this is the second complex-title'])

    def test_by_type(self):
        self._check_equal(
            {'type': 'movie-hdrip'},
            ['another movie-hdrip', 'sample movie-hdrip'])

    def test_by_min(self):
        self._check_equal(
            {'size_min': '11M'},
            ['the big one'])

    def test_by_max(self):
        self._check_equal(
            {'size_max': '11M'},
            ['the little one'])

    def test_regex(self):
        self._check_equal(
            {'name_regexp': r'title\s+(a|C)'},
            ['title A', 'title C'])

    def test_composed(self):
        self._check_equal(
            {'name_like': 'title %'},
            ['title A', 'title B', 'title C', 'title D'])

        self._check_equal(
            {'name_like': 'title %', 'type': 'movie'},
            ['title C'])


if __name__ == '__main__':
    unittest.main()
