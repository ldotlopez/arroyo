# -*- coding: utf-8 -*-
# [SublimeLinter pep8-max-line-length:160 flake8-max-line-length:160]
# vim: set fileencoding=utf-8 :

import unittest
import time

from testapp import TestApp, mock_source
from arroyo import models


class BaseTest:
    slowdown = None

    def wait(self):
        if self.slowdown:
            time.sleep(self.slowdown)

    def setUp(self):
        settings = {'plugins.' + k + '.enabled': True for k in self.plugins}
        # settings['log-level'] = 'CRITICAL'
        settings['downloader'] = self.downloader
        self.app = TestApp(settings)

    def tearDown(self):
        for src in self.app.downloads.list():
            self.app.downloads.remove(src)
        self.wait()

    def test_add(self):
        src1 = mock_source('foo')
        self.app.insert_sources(src1)

        self.app.downloads.add(src1)

        self.wait()
        self.assertEqual(
            set(self.app.downloads.list()),
            set([src1]))

    def test_remove(self):
        src1 = mock_source('foo')
        src2 = mock_source('bar')
        self.app.insert_sources(src1, src2)

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
        src1 = mock_source('foo')
        src2 = mock_source('bar')
        self.app.insert_sources(src1, src2)

        self.app.downloads.add(src1)

        self.wait()
        self.app.downloads.remove(src2)

    def test_duplicates(self):
        src1 = mock_source('foo')
        self.app.insert_sources(src1)

        self.app.downloads.add(src1)
        self.app.downloads.add(src1)

        self.wait()
        self.assertEqual(
            set(self.app.downloads.list()),
            set([src1]))

    def test_unexpected_add(self):
        src1 = mock_source('foo')
        src2 = mock_source('bar')

        # Important: src2 is not added because it should
        # be really unexpected. Adding a known source is another test
        self.app.insert_sources(src1)

        self.app.downloads.add(src1)
        self.app.downloads.backend.add(src2)

        self.wait()
        self.assertEqual(
            set(self.app.downloads.list()),
            set([src1]))

    def test_unexpected_remove(self):
        src1 = mock_source('foo')
        src2 = mock_source('bar')
        self.app.insert_sources(src1, src2)

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
        src1 = mock_source('foo')
        src2 = mock_source('bar')
        self.app.insert_sources(src1, src2)

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

    def test_info(self):
        src = mock_source('foo')
        self.app.insert_sources(src)
        self.app.downloads.add(src)
        self.app.downloads.get_info(src)


class MockTest(BaseTest, unittest.TestCase):
    plugins = ['downloaders.mock']
    downloader = 'mock'


class TransmissionTest(BaseTest, unittest.TestCase):
    plugins = ['downloaders.transmission']
    downloader = 'transmission'
    slowdown = 0.5

if __name__ == '__main__':
    unittest.main()
