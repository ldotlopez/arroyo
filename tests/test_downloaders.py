# -*- coding: utf-8 -*-
# [SublimeLinter pep8-max-line-length:160 flake8-max-line-length:160]
# vim: set fileencoding=utf-8 :

import unittest
import time

from arroyo import core, models


def src(name, **kwsrc):
    return models.Source.from_data(name, **kwsrc)


class BaseTest:
    slowdown = None

    def wait(self):
        if self.slowdown:
            time.sleep(self.slowdown)

    def setUp(self):
        settings = core.build_basic_settings()

        settings.set('mediainfo', False)
        settings.set('log-level', 'CRITICAL')
        settings.set('db-uri', 'sqlite:///:memory:')
        settings.set('downloader', self.backend)

        app = core.Arroyo(settings)
        self.app = app

    def tearDown(self):
        for src in self.app.downloads.list():
            self.app.downloads.remove(src)
        self.wait()

    def init_db(self, srcs):
        for src in srcs:
            self.app.db.session.add(src)
            if src.type:
                self.app.mediainfo.process(src)

        self.app.db.session.commit()

    def test_add(self):
        src1 = src('foo')
        self.init_db([src1])

        self.app.downloads.add(src1)

        self.wait()
        self.assertEqual(
            set(self.app.downloads.list()),
            set([src1]))

    def test_remove(self):
        src1 = src('foo')
        src2 = src('bar')
        self.init_db([src1, src2])

        self.app.downloads.add(src1)
        self.app.downloads.add(src2)

        self.wait()
        self.assertEqual(
            set(self.app.downloads.list()),
            set([src1, src2]))

        self.app.downloads.remove(src1)

        self.wait()
        self.assertEqual(
            set(self.app.downloads.list()),
            set([src2]))

    def test_fail_remove(self):
        src1 = src('foo')
        src2 = src('bar')
        self.init_db([src1, src2])

        self.app.downloads.add(src1)

        self.wait()
        self.app.downloads.remove(src2)

    def test_duplicates(self):
        src1 = src('foo')
        self.init_db([src1])

        self.app.downloads.add(src1)
        self.app.downloads.add(src1)

        self.wait()
        self.assertEqual(
            set(self.app.downloads.list()),
            set([src1]))

    def test_unexpected_add(self):
        src1 = src('foo')
        src2 = src('bar')

        # Important: src2 is not added because it should
        # be really unexpected. Adding a known source is another test
        self.init_db([src1])

        self.app.downloads.add(src1)
        self.app.downloads.backend.add(src2)

        self.wait()
        self.assertEqual(
            set(self.app.downloads.list()),
            set([src1]))

    def test_unexpected_remove(self):
        src1 = src('foo')
        src2 = src('bar')
        self.init_db([src1, src2])

        self.app.downloads.add(src1)
        self.app.downloads.add(src2)

        self.wait()
        dler_item = self.app.downloads.get_translations()[src2]
        self.app.downloads.backend.remove(dler_item)

        self.wait()
        self.assertEqual(
            set(self.app.downloads.list()),
            set([src1]))

    def test_archive_after_manual_remove(self):
        src1 = src('foo')
        src2 = src('bar')
        self.init_db([src1, src2])

        self.app.downloads.add(src1)
        self.app.downloads.add(src2)

        self.wait()
        dler_item = self.app.downloads.get_translations()[src2]
        self.app.downloads.backend.remove(dler_item)

        self.wait()
        self.app.downloads.list()

        self.wait()
        self.assertEqual(
            src2.state,
            models.Source.State.ARCHIVED)


class MockDownloaderTest(BaseTest, unittest.TestCase):
    backend = 'mock'


class TransmissionDownloaderTest(BaseTest, unittest.TestCase):
    backend = 'transmission'
    slowdown = 0.5

if __name__ == '__main__':
    unittest.main()
