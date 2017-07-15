# -*- coding: utf-8 -*-

# Copyright (C) 2015 Luis López <luis@cuarentaydos.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301,
# USA.


import unittest
from unittest import mock
import time


from testapp import TestApp, mock_source
from arroyo import (
    downloads,
    models
)


class BaseTest:
    SLOWDOWN = None

    def wait(self):
        if self.SLOWDOWN:
            time.sleep(self.SLOWDOWN)

    def setUp(self):
        settings = {'plugins.' + k + '.enabled': True
                    for k in self.PLUGINS}
        settings['downloader'] = self.DOWNLOADER
        self.app = TestApp(settings)

    def test_add(self):
        src1 = mock_source('foo')
        self.app.insert_sources(src1)
        self.app.downloads.add(src1)
        self.wait()

        self.assertTrue(
            src1.download.state >= models.State.INITIALIZING
        )
        self.assertEqual(
            set(self.app.downloads.list()),
            set([src1])
        )

    def test_add_duplicated(self):
        src1 = mock_source('foo')
        self.app.insert_sources(src1)
        self.app.downloads.add(src1)
        self.wait()

        with self.assertRaises(downloads.DuplicatedDownloadError):
            self.app.downloads.add(src1)

        self.assertEqual(
            set(self.app.downloads.list()),
            set([src1]))

    def test_add_duplicated_archived(self):
        src1 = mock_source('foo')
        self.app.insert_sources(src1)
        self.app.downloads.add(src1)
        self.app.downloads.archive(src1)
        self.wait()

        with self.assertRaises(downloads.DuplicatedDownloadError):
            self.app.downloads.add(src1)

        self.assertEqual(
            self.app.downloads.list(),
            [])

    def test_cancel(self):
        src1 = mock_source('foo')
        self.app.insert_sources(src1)
        self.app.downloads.add(src1)
        self.app.downloads.cancel(src1)
        self.wait()

        self.assertEqual(
            src1.download,
            None)
        self.assertEqual(
            self.app.downloads.list(),
            [])

    def test_archive(self):
        src1 = mock_source('foo')
        self.app.insert_sources(src1)
        self.app.downloads.add(src1)
        self.app.downloads.archive(src1)
        self.wait()

        self.assertEqual(
            src1.download.state,
            models.State.ARCHIVED)
        self.assertEqual(
            self.app.downloads.list(),
            [])

    def test_remove_unknown_source(self):
        src1 = mock_source('foo')
        src2 = mock_source('bar')
        self.app.insert_sources(src1, src2)
        self.wait()

        with self.assertRaises(downloads.DownloadNotFoundError):
            self.app.downloads.cancel(src1)
        with self.assertRaises(downloads.DownloadNotFoundError):
            self.app.downloads.archive(src2)

    def plugin_class(self):
        return self.app._get_extension_class(downloads.Downloader,
                                             self.DOWNLOADER)

    def foreign_ids(self, srcs):
        return [self.app.downloads.plugin.id_for_source(src)
                for src in srcs]

    def test_unexpected_download_from_plugin(self):
        src1 = mock_source('foo')
        src2 = mock_source('bar')
        self.app.insert_sources(src1)
        self.app.downloads.add(src1)
        self.wait()

        fake_list = self.foreign_ids([src1, src2])
        with mock.patch.object(self.plugin_class(), 'list',
                               return_value=fake_list):
            self.assertEqual(
                set(self.app.downloads.list()),
                set([src1]))

    def test_handle_unexpected_remove_from_plugin_as_cancel(self):
        src1 = mock_source('foo')
        src2 = mock_source('bar')
        self.app.insert_sources(src1, src2)
        self.app.downloads.add(src1)
        self.app.downloads.add(src2)
        self.wait()

        fake_list = self.foreign_ids([src1])
        with mock.patch.object(self.plugin_class(), 'list',
                               return_value=fake_list):

            self.app.downloads.sync()

        self.assertEqual(
            src2.download,
            None)

    def test_handle_unexpected_remove_from_plugin_as_archive(self):
        src1 = mock_source('foo')
        src2 = mock_source('bar')
        self.app.insert_sources(src1, src2)
        self.app.downloads.add(src1)
        self.app.downloads.add(src2)
        self.wait()

        # Manually update state of src2
        src2.download.state = models.State.SHARING

        # Mock plugin list to not list src2
        fake_list = self.foreign_ids([src1])
        with mock.patch.object(self.plugin_class(), 'list',
                               return_value=fake_list):
            self.app.downloads.sync()

        self.assertEqual(
            src2.download.state,
            models.State.ARCHIVED
        )

    def test_info(self):
        src = mock_source('foo')
        self.app.insert_sources(src)
        self.app.downloads.add(src)
        self.app.downloads.get_info(src)


class MockTest(BaseTest, unittest.TestCase):
    PLUGINS = ['downloaders.mock']
    DOWNLOADER = 'mock'
    DOWNLOADER_CLASS = 'arroyo.plugins.downloaders.mock.MockDownloader'


class TransmissionTest(BaseTest, unittest.TestCase):
    PLUGINS = ['downloaders.transmission']
    DOWNLOADER = 'transmission'
    SLOWDOWN = 0.2

    def setUp(self):
        super().setUp()
        for t in self.app.downloads.plugin.api.get_torrents():
            if t.name in ['foo', 'bar']:
                self.app.downloads.plugin.api.remove_torrent(
                    t.id, delete_data=True)
        self.wait()


class DirectoryTest(BaseTest, unittest.TestCase):
    # TODO:
    # - Set storage path to tmpdir

    PLUGINS = ['downloaders.directory']
    DOWNLOADER = 'directory'
    SLOWDOWN = 0.2

    def setUp(self):
        super().setUp()
        cls = self.plugin_class()
        cls._fetch_torrent = mock.Mock(return_value=b'')

if __name__ == '__main__':
    unittest.main()
