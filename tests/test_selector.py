# -*- coding: utf-8 -*-
# [SublimeLinter pep8-max-line-length:160 flake8-max-line-length:160]
# vim: set fileencoding=utf-8 :

import unittest

from arroyo import (
    models,
    selector
)
import testapp


class SelectorInterfaceTest(unittest.TestCase):
    def test_get_queries(self):
        app = testapp.TestApp({
            'plugin.sourcequery.enabled': True,
            'plugin.moviequery.enabled': True,

            'query.test1.name-glob': '*x*',
            'query.test2.kind': 'movie',
            'query.test2.title': 'foo',
            })

        queries = {q.name: q for q in app.selector.get_queries()}

        self.assertTrue('test1' in queries)
        self.assertTrue('test2' in queries)
        self.assertTrue(len(queries.keys()) == 2)

    def test_get_queries_with_defaults(self):
        app = testapp.TestApp({
            'plugin.sourcequery.enabled': True,
            'plugin.moviequery.enabled': True,

            'selector.query-defaults.since': 1234567890,
            'selector.query-defaults.language': 'eng-us',
            'selector.query-movie-defaults.quality': '720p',

            'query.test1.name': 'foo',

            'query.test2.kind': 'movie',
            'query.test2.title': 'bar'
        })

        queries = {q.name: q for q in app.selector.get_queries()}

        self.assertEqual(
            queries['test1'].params.get('language', None),
            'eng-us')
        self.assertTrue(
            'quality' not in queries['test1'].params)

        self.assertTrue(
            'quality' in queries['test2'].params)
        self.assertTrue(
            'since' in queries['test2'].params)

    def test_get_query_from_user_spec(self):
        app = testapp.TestApp({
            'plugin.sourcequery.enabled': True,

            'selector.query-defaults.since': 1234567890,
            'selector.query-defaults.since': 1234567890,
        })

        user_spec = selector.QuerySpec('test', name_glob='*foo*')
        query = app.selector.get_query_for_spec(user_spec)

        self.assertTrue('since' in query.spec)

    def test_download_only_once(self):
        s = testapp.mock_source
        srcs = [
            s('Foo s03e04.mp4', type='episode'),
        ]

        app = testapp.TestApp({
            'plugin.episodequery.enabled': True,

            'plugin.sourcefilters.enabled': True,
            'plugin.episodefilters.enabled': True,

            'plugin.basicsorter.enabled': True,

            'plugin.mockdownloader.enabled': True,

            'downloader': 'mock'
        })
        app.insert_sources(*srcs)

        query = app.selector.get_query_from_params(
            params=dict(kind='episode', series='Foo')
        )
        matches = app.selector.matches(query)
        choosen = app.selector.select_single(matches)
        app.downloads.add(choosen)

        matches = list(app.selector.matches(query))
        self.assertEqual(matches, [])


class SelectorTestCase(unittest.TestCase):
    def assertQuery(self, expected, **params):
        spec = selector.QuerySpec('test', **params)
        res = self.app.selector.matches(spec, everything=False)
        self.assertEqual(
            set([x.name for x in expected]),
            set([x.name for x in res])
        )


class SourceSelectorTest(SelectorTestCase):
    def setUp(self):
        self.app = testapp.TestApp({
            'plugin.sourcequery.enabled': True,
            'plugin.sourcefilters.enabled': True
        })

    def test_not_everything(self):
        srcs = [
            testapp.mock_source('foo'),
            testapp.mock_source('bar'),
            testapp.mock_source('baz')
        ]
        self.app.insert_sources(*srcs)
        self.assertQuery(srcs, name_glob='*')

        for src in srcs:
            src.state = models.Source.State.DOWNLOADING
            self.app.db.session.add(src)

        self.app.db.session.commit()

        self.assertQuery([], name_glob='*')

    def test_name_glob(self):
        expected = [
            testapp.mock_source('Interstellar [BluRay Rip][Español Latino][2014]'),
            testapp.mock_source('Interstellar (2014) 720p BrRip x264 - YIFY'),
            testapp.mock_source('Interstellar 2014 TRUEFRENCH BRRip XviD-Slay3R avi')
        ]
        other = [
            testapp.mock_source('Game of Thrones S05E05 HDTV x264-ASAP[ettv]')
        ]
        self.app.insert_sources(*(expected + other))

        self.assertQuery(
            expected,
            name_glob='*interstellar*')

        self.assertQuery(
            [],
            name_glob='nothing matches')

    def test_source_language(self):
        eng = [
            testapp.mock_source('Game of Thrones S05E08 1080p HDTV x264', language='eng-us')
        ]
        esp = [
            testapp.mock_source('Game of Thrones S05E08 SPANISH ESPAÑOL 720p HDTV x264', language='esp-es')
        ]
        undef = [
            testapp.mock_source('Game of Thrones S05E08 720p HDTV x264')
        ]
        self.app.insert_sources(*(eng + esp + undef))

        self.assertQuery(
            eng + esp + undef,
            name_glob='*game.of.thrones*')

        self.assertQuery(
            eng,
            name_glob='*game.of.thrones*', language='eng-us')

        self.assertQuery(
            esp,
            name_glob='*game.of.thrones*', language='esp-es')


class MediainfoFiltersTest(SelectorTestCase):
    def setUp(self):
        self.app = testapp.TestApp({
            'plugin.sourcequery.enabled': True,
            'plugin.episodequery.enabled': True,
            'plugin.mediainfofilters.enabled': True
        })

    def test_quality(self):
        hdready = [
            testapp.mock_source('Game Of Thrones S05E05 720p HDTV x264-0SEC[rarbg]', type='episode')
        ]
        hdtv = [
            testapp.mock_source('Game of Thrones S05E02 HDTV x264-Xclusive [eztv]')
        ]
        self.app.insert_sources(*(hdtv + hdready))
        self.app.mediainfo.process(*(hdtv + hdready))  # Force mediainfo processing

        self.assertQuery(
            [],
            quality='1080p')

        self.assertQuery(
            hdready,
            quality='720p')

        self.assertQuery(
            hdtv,
            quality='hdtv')

    def test_codec(self):
        xvid = [
            testapp.mock_source('The.Big.Bang.Theory.S09E05.HDTV.XviD-FUM[ettv]', type='episode')
        ]
        x264 = [
            testapp.mock_source('The.Last.Man.On.Earth.S02E04.HDTV.x264-KILLERS[ettv]', type='episode')
        ]
        srcs = xvid + x264
        self.app.insert_sources(*srcs)
        self.app.mediainfo.process(*srcs)  # Force mediainfo processing

        self.assertQuery(
            [],
            codec='foo')

        self.assertQuery(
            xvid,
            codec='xvid')

        self.assertQuery(
            x264,
            codec='h264')


class EpisodeSelectorTest(SelectorTestCase):
    def setUp(self):
        self.app = testapp.TestApp({
            'plugin.episodequery.enabled': True,
            'plugin.sourcefilters.enabled': True,
            'plugin.episodefilters.enabled': True,
            'plugin.mediainfofilters.enabled': True,
            'plugin.basicsorter.enabled': True
        })

    def test_series(self):
        srcs = [
            # episode from GoT
            testapp.mock_source('Game of Thrones S05E02 HDTV x264-Xclusive [eztv]', type='episode'),
            # one movie
            testapp.mock_source('Interstellar [BluRay Rip][Español Latino][2014]', type='movie'),
            # episode from another series
            testapp.mock_source('Arrow S03E22 HDTV x264-LOL[ettv]', type='episode'),
            # episode without type info
            testapp.mock_source('Game Of Thrones S05E05 720p HDTV x264-0SEC[rarbg]')
        ]
        self.app.insert_sources(*srcs)

        self.assertQuery(
            [srcs[0], srcs[2]],
            kind='episode', series='*')

        self.assertQuery(
            [srcs[0]],
            kind='episode', series='game of thrones')

        srcs[0].state = models.Source.State.DONE

        self.assertQuery(
            [srcs[2]],
            kind='episode', series='*')

        self.assertQuery(
            [],
            kind='episode', series='game of thrones')

    def test_real_world_first_use(self):
        s = testapp.mock_source
        srcs = [
            s('Game of Thrones S05E01 HDTV', type='episode'),
            s('Game of Thrones S05E01 720p', type='episode'),
            s('Game of Thrones S05E02 HDTV', type='episode'),
            s('Game of Thrones S05E02 720p', type='episode'),
            s('Game of Thrones S05E03 HDTV', type='episode'),
            s('Game of Thrones S05E03 720p', type='episode'),
            s('Arrow S03E22 FuM XViD HDTV', type='episode'),
            s('Arrow S03E23 FuM XViD', type='episode'),
        ]
        self.app.insert_sources(*srcs)

        # All GoT episodes match
        self.assertQuery(
            srcs[:5:2],
            kind='episode', series='game of thrones', quality='hdtv')

        # After this state change nothing matches
        for src in srcs:
            src.state = models.Source.State.DONE
        self.assertQuery(
            [],
            kind='episode', series='game of thrones', quality='hdtv')

        # Adding a new version from existings episode should be matched
        new_source = s('Game of Thrones S05E01 HDTV PROPER', type='episode')
        self.app.insert_sources(new_source,)
        self.assertQuery(
            [new_source],
            kind='episode', series='game of thrones', quality='hdtv')

        # Revert src states and link episodes with sources
        for src in srcs:
            src.state = models.Source.State.NONE
        spec = selector.QuerySpec('test', kind='episode', series='game of thrones', quality='hdtv')
        matches = self.app.selector.matches(spec)
        srcs = self.app.selector.select(matches)
        for src in self.app.selector.select(srcs):
            src.episode.selection = models.EpisodeSelection(source=src)

        # Check or queryspec again
        self.assertQuery(
            [],
            kind='episode', series='game of thrones', quality='hdtv')

        # And with new sources?
        new_source = s('Game of Thrones S05E01 HDTV LoL x264', type='episode')
        self.app.insert_sources(new_source,)
        self.assertQuery(
            [],
            kind='episode', series='game of thrones', quality='hdtv')

        # But… let's check with new episode
        new_source = s('Game of Thrones S05E04 HDTV LoL x264', type='episode')
        self.app.insert_sources(new_source,)
        self.assertQuery(
            [new_source],
            kind='episode', series='game of thrones', quality='hdtv')

    def test_basic_sorter(self):
        s = testapp.mock_source
        srcs = [
            s('True Detective S02E04 720p HDTV x264-0SEC [GloDLS]', type='episode', seeds=1, leechers=0, language='eng-us'),
            s('True.Detective.S02E04.720p.HDTV.x264-0SEC [b2ride]', type='episode', seeds=176, leechers=110, language='eng-us'),
            s('True Detective S02E04 720p HDTV x264-0SEC[rartv]', type='episode', seeds=3498, leechers=5171, language='eng-us'),
            s('True Detective S02E04 INTERNAL HDTV x264-BATV', type='episode', language='eng-us'),
            s('True Detective S02E04 720p HDTV x264-0SEC', type='episode', language='eng-us'),
            s('True Detective S02E04 HDTV x264-ASAP', type='episode', language='eng-us'),
            s('True Detective S02E04 INTERNAL HDTV x264-BATV[ettv]', type='episode', seeds=17, leechers=197, language='eng-us'),
        ]
        spec = selector.QuerySpec('test', kind='episode', series='true detective', quality='720p', language='eng-us')
        app = testapp.TestApp({
            'plugin.episodequery.enabled': True,
            'plugin.sourcefilters.enabled': True,
            'plugin.episodefilters.enabled': True,
            'plugin.mediainfofilters.enabled': True,
            'plugin.basicsorter.enabled': True,
        })
        app.insert_sources(*srcs)
        matches = list(app.selector.matches(spec))
        self.assertEqual(len(matches), 4)

        sort = app.selector.sort(matches)
        self.assertEqual([x.name for x in sort], [
            'True.Detective.S02E04.720p.HDTV.x264-0SEC [b2ride]',
            'True Detective S02E04 720p HDTV x264-0SEC[rartv]',
            'True Detective S02E04 720p HDTV x264-0SEC [GloDLS]',
            'True Detective S02E04 720p HDTV x264-0SEC'])

    def test_multicase_series(self):
        s = testapp.mock_source
        srcs = [
            s('Foo s03e04.mp4', type='episode'),
            s('The Last Man on Earth S02E16 Falling Slowly WEB-DL x264 AAC', type='episode'),
            s('The Last Man On Earth S02E16 HDTV x264-FLEET[rartv]', type='episode'),
            s('The last man on earth - S02E16 - 576P - SweSub.mp4', type='episode'),
            s('The Last Man On Earth S02E17 HDTV XviD-AFG', type='episode'),
            s('The Last Man on Earth S02E17 Smart and Stupid WEB-DL x264 AAC', type='episode'),
            s('The last man on earth - S02E17 - 576P - SweSub.mp4', type='episode'),
            s('The Last Man on Earth S02E18 720p HDTV x265 HEVC - YSTEAM', type='episode'),
            s('The Last Man On Earth S02E18 FASTSUB VOSTFR HDTV XviD-ZT avi', type='episode'),
            s('The last man on earth - S02E18 - 576P - SweSub.mp4', type='episode'),
            s('The Last Man On Earth Season 2 1080/HDTV')
        ]

        app = testapp.TestApp({
            'plugin.episodequery.enabled': True,
            'plugin.sourcefilters.enabled': True,
            'plugin.episodefilters.enabled': True,
            'plugin.mediainfofilters.enabled': True,
            'plugin.basicsorter.enabled': True,
        })
        app.insert_sources(*srcs)

        spec = selector.QuerySpec('test', kind='episode', series='the last man on earth')

        matches = list(app.selector.matches(spec))
        self.assertEqual(len(matches), 9)

        candidates = list(app.selector.select(matches))
        self.assertEqual(len(candidates), 3)


if __name__ == '__main__':
    unittest.main()
