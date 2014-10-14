# -*- coding: utf-8 -*-
# [SublimeLinter pep8-max-line-length:119]
# vim: set fileencoding=utf-8 :

import unittest

from ldotcommons import sqlalchemy as ldotsa

from arroyo import db
from arroyo.downloaders import mock


class TestDownloader(unittest.TestCase):
    def setUp(self):
        self.sess = ldotsa.create_session('sqlite:///:memory:')
        for i in range(1, 4):
            data = db.source_data_builder(name='test {}'.format(i))
            self.sess.add(db.Source(**data))
        self.sess.commit()

        self.dler = mock.Downloader(session=self.sess)
        for x in self.dler.list():
            self.dler.remove(x)

    def tearDown(self):
        for x in self.dler.list():
            self.dler.remove(x)

    def test_add(self):
        l = self.dler.list()
        self.assertEqual(len(l), 0)

        t = self.sess.query(db.Source).filter(db.Source.name == 'test 1').one()
        tid = self.dler.add(t)

        self.assertIsNotNone(tid)
        self.assertEqual(self.dler.list(), [t])

    def test_remove(self):
        (t1, t2, t3) = self.sess.query(db.Source).all()
        for t in (t1, t2, t3):
            self.dler.add(t)

        self.dler.remove(t2)
        self.assertEqual(
            sorted(self.dler.list()),
            sorted([t1, t3]))


if __name__ == '__main__':
    unittest.main()
