# -*- coding: utf-8 -*-
# [SublimeLinter pep8-max-line-length:160 flake8-max-line-length:160]
# vim: set fileencoding=utf-8 :

import unittest

from arroyo import core, models


def src(name, **kwsrc):
    return models.Source.from_data(name, **kwsrc)


class SelectorTest(unittest.TestCase):
    def setUp(self):
        settings = core.build_basic_settings()

        settings.set('mediainfo', False)
        settings.set('log-level', 'CRITICAL')
        settings.set('db-uri', 'sqlite:///:memory:')
        settings.set('downloader', 'transmission')

        app = core.Arroyo(settings)
        self.app = app

    def tearDown(self):
        for src in self.app.downloads.list():
            self.app.downloads.remove(src)

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
        self.assertEqual(
            set(self.app.downloads.list()),
            set([src1]))

    def test_remove(self):
        src1 = src('foo')
        src2 = src('bar')
        self.init_db([src1, src2])

        self.app.downloads.add(src1)
        self.app.downloads.add(src2)
        self.assertEqual(
            set(self.app.downloads.list()),
            set([src1, src2]))

        self.app.downloads.remove(src1)
        # import time
        # time.sleep(1)
        self.assertEqual(
            set(self.app.downloads.list()),
            set([src2]))

    def test_duplicates(self):
        src1 = src('foo')
        self.init_db([src1])

        self.app.downloads.add(src1)
        self.app.downloads.add(src1)
        self.assertEqual(
            set(self.app.downloads.list()),
            set([src1]))

if __name__ == '__main__':
    unittest.main()
