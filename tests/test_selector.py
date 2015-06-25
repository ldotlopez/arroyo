# -*- coding: utf-8 -*-
# [SublimeLinter pep8-max-line-length:160 flake8-max-line-length:160]
# vim: set fileencoding=utf-8 :

import unittest

from arroyo import core, models, selector


def src(name, **kwsrc):
    return models.Source.from_data(name, **kwsrc)


class SelectorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        settings = core.build_basic_settings()

        settings.set('mediainfo', False)
        settings.set('log-level', 'CRITICAL')
        settings.set('db-uri', 'sqlite:///:memory:')

        app = core.Arroyo(settings)
        cls.app = app

    def setUp(self):
        self.app = self.__class__.app

    def tearDown(self):
        self.app.db.reset()

    def init_db(self, srcs):
        for src in srcs:
            self.app.db.session.add(src)
            if src.type:
                self.app.mediainfo.process(src)

        self.app.db.session.commit()

    def assertQuery(self, query, expected):
        self.assertEqual(
            set([x.name for x in expected]),
            set([x.name for x in self.app.selector.select(query)])
        )


class SourceSelectorTest(SelectorTest):
    def test_name_like(self):
        expected = [
            src('Interstellar [BluRay Rip][Español Latino][2014]'),
            src('Interstellar (2014) 720p BrRip x264 - YIFY'),
            src('Interstellar 2014 TRUEFRENCH BRRip XviD-Slay3R avi')
        ]
        other = [
            src('Game of Thrones S05E05 HDTV x264-ASAP[ettv]')
        ]

        self.init_db(expected + other)

        self.assertQuery(
            selector.QuerySpec(name_like='interstellar'),
            expected)

        self.assertQuery(
            selector.QuerySpec(name_like='none'),
            [])

    def test_source_language(self):
        eng = [
            src('Game of Thrones S05E08 1080p HDTV x264', language='eng-us')
        ]
        esp = [
            src('Game of Thrones S05E08 SPANISH ESPAÑOL 720p HDTV x264', language='esp-es')
        ]
        undef = [
            src('Game of Thrones S05E08 720p HDTV x264')
        ]
        self.init_db(eng + esp + undef)

        self.assertQuery(
            selector.QuerySpec(name_like='game of thrones'),
            eng + esp + undef
        )
        self.assertQuery(
            selector.QuerySpec(name_like='game of thrones', language='eng-us'),
            eng
        )
        self.assertQuery(
            selector.QuerySpec(name_like='game of thrones', language='esp-es'),
            esp
        )


class EpisodeSelectorTest(SelectorTest):
    def test_series(self):
        expected = [
            src('Game of Thrones S05E02 HDTV x264-Xclusive [eztv]', type='episode')
        ]
        other = [
            # one movie
            src('Interstellar [BluRay Rip][Español Latino][2014]', type='movie'),
            # episode from another series
            src('Arrow S03E22 HDTV x264-LOL[ettv]', type='episode'),
            # episode without type info
            src('Game Of Thrones S05E05 720p HDTV x264-0SEC[rarbg]')
        ]
        self.init_db(expected + other)

        self.assertQuery(
            selector.QuerySpec(selector='episode', series='game of thrones'),
            expected)

        # expected[0].state = models.Source.State.DONE
        # self.assertQuery(
        #     selector.QuerySpec(selector='episode', series='game of thrones'),
        #     [])

    def test_quality(self):
        hdready = [
            src('Game Of Thrones S05E05 720p HDTV x264-0SEC[rarbg]', type='episode')
        ]
        hdtv = [
            src('Game of Thrones S05E02 HDTV x264-Xclusive [eztv]', type='episode')
        ]

        self.init_db(hdready + hdtv)

        self.assertQuery(
            selector.QuerySpec(selector='episode', series='game of thrones'),
            hdtv + hdready)

        self.assertQuery(
            selector.QuerySpec(selector='episode', series='game of thrones', quality='1080p'),
            [])

        self.assertQuery(
            selector.QuerySpec(selector='episode', series='game of thrones', quality='720p'),
            hdready)

        self.assertQuery(
            selector.QuerySpec(selector='episode', series='game of thrones', quality='hdtv'),
            hdtv)

    def test_everything(self):
        x = [
            src('Game Of Thrones S01E01 720p', type='episode'),
            src('Game Of Thrones S01E01 HDTV', type='episode'),
            src('Game Of Thrones S01E02 720p', type='episode'),
            src('Game Of Thrones S01E02 HDTV', type='episode'),
            src('Game Of Thrones S02E01 720p', type='episode'),
            src('Game Of Thrones S02E01 HDTV', type='episode'),
        ]
        self.init_db(x)

        q = selector.QuerySpec(selector='episode', series='game of thrones', season=1)
        res = list(self.app.selector.select(q))
        self.assertTrue(
            (x[0] in res or x[1] in res) and (x[2] in res or x[3] in res)
        )

        q = selector.QuerySpec(selector='episode', series='game of thrones', season=1)
        res = list(self.app.selector.select(q, everything=True))
        self.assertTrue(set(res), set(x[0:3]))

    def test_selection(self):
        x = [
            src('Game Of Thrones S01E01 720p', type='episode'),
            src('Game Of Thrones S01E02 720p', type='episode'),
        ]
        self.init_db(x)
        x[0].episode.selection = models.EpisodeSelection()
        x[0].episode.selection.source = x[0]
        self.app.db.session.commit()

        q = selector.QuerySpec(selector='episode', series='game of thrones')
        res = list(self.app.selector.select(q, everything=True))
        self.assertTrue(set(res), set(x))

        q = selector.QuerySpec(selector='episode', series='game of thrones')
        res = list(self.app.selector.select(q))
        self.assertTrue(set(res), set(x[1]))

    def test_proper(self):
        x = [
            src('Game Of Thrones S01E01 720p', type='episode'),
            src('Game Of Thrones S01E01 REPACK 720p', type='episode'),
        ]
        self.init_db(x)

        q = selector.QuerySpec(selector='episode', series='game of thrones')
        res = list(self.app.selector.select(q))
        self.assertEqual(set(res[0]), set(x[1]))

if __name__ == '__main__':
    unittest.main()
