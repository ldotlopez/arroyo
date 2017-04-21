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
import testapp


from arroyo import models


class QueryBuilderTest(unittest.TestCase):
    def test_episode_search(self):
        app = testapp.TestApp()
        q1 = app.selector.query_from_args(keyword='the oa 3x02')
        q2 = app.selector.query_from_args(keyword='the oa s03e02')
        q3 = app.selector.query_from_args(keyword='the oa s03 e02')

        self.assertEqual(q1.asdict(), dict(
            type='episode',
            series='the oa',
            season='3',
            number='2',
            state='none'
        ))
        self.assertEqual(q1, q2)
        self.assertEqual(q1, q3)

        q_as_source = app.selector.query_from_args(
            keyword='the oa   3x02  ',
            params={'type': 'source'}
        )
        self.assertEqual(
            q_as_source.asdict(),
            {'name-glob': '*the*oa*3x02*', 'type': 'source', 'state': 'none'}
        )

    def test_movie(self):
        app = testapp.TestApp()

        q1 = app.selector.query_from_args(keyword='Flash Gordon 1980')
        q2 = app.selector.query_from_args(keyword='Flash Gordon (1980)')

        self.assertEqual(q1.asdict(), dict(
            type='movie',
            title='flash gordon',
            year='1980',
            state='none'
        ))
        self.assertEqual(q1, q2)

        q = app.selector.query_from_args(keyword='Flash gordon')
        self.assertEqual(
            q.asdict(),
            {'name-glob': '*flash*gordon*', 'type': 'source', 'state': 'none'}
        )

    def test_mediainfo(self):
        app = testapp.TestApp({
            'plugins.filters.mediainfo.enabled': True
        })
        q = app.selector.query_from_args(keyword='series s01e01 720p x264 FuM[ettv]')
        self.assertEqual(
            q['quality'], '720p'
        )
        self.assertEqual(
            q['codec'], 'h264'  # x264 is detected as h264
        )


class SelectorInterfaceTest(unittest.TestCase):
    def test_get_queries(self):
        app = testapp.TestApp({
            'query.test1.name-glob': '*x*',
            'query.test2.type': 'movie',
            'query.test2.title': 'foo',
            })

        queries = {
            name: query
            for (name, query) in
            app.selector.queries_from_config()
        }

        self.assertTrue('test1' in queries)
        self.assertTrue('test2' in queries)
        self.assertTrue(len(queries.keys()) == 2)

    def test_get_queries_with_defaults(self):
        app = testapp.TestApp({
            'selector.query-defaults.since': 1234567890,
            'selector.query-defaults.language': 'eng-us',
            'selector.query-movie-defaults.quality': '720p',

            'query.test1.name': 'foo',

            'query.test2.type': 'movie',
            'query.test2.title': 'bar'
        })

        queries = {
            name: query
            for (name, query) in
            app.selector.queries_from_config()
        }

        self.assertEqual(
            queries['test1'].get('language', None),
            'eng-us')
        self.assertTrue(
            'quality' not in queries['test1'])

        self.assertTrue(
            'quality' in queries['test2'])
        self.assertTrue(
            'since' in queries['test2'])

    def test_include_defaults_in_query(self):
        app = testapp.TestApp({
            'selector.query-defaults.since': 1234567890,
        })

        query = app.selector.query_from_args(params={'name_glob': '*foo*'})

        self.assertTrue('since' in query)


class SelectorTestCase(unittest.TestCase):
    def assertQuery(self, expected, **params):
        query = self.app.selector.query_from_args(params=dict(**params))
        res = self.app.selector.matches(query)
        self.assertEqual(
            set([x.name for x in expected]),
            set([x.name for x in res])
        )


class SourceSelectorTest(SelectorTestCase):
    def setUp(self):
        self.app = testapp.TestApp({
            'plugins.filters.sourcefields.enabled': True,
        })

    def test_exclude_state_not_none(self):
        srcs = [
            testapp.mock_source('foo'),
            testapp.mock_source('bar'),
            testapp.mock_source('baz')
        ]
        self.app.insert_sources(*srcs)
        self.assertQuery(srcs, name_glob='*')

        for src in srcs:
            src.state = models.State.DOWNLOADING
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
            'plugins.filters.sourcefields.enabled': True,
            'plugins.filters.episodefields.enabled': True,
            'plugins.filters.moviefields.enabled': True,
            'plugins.filters.mediainfo.enabled': True
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

    def test_release_group(self):
        dimension = testapp.mock_source('2.Broke.Girls.S06E16.720p.HDTV.X264-DIMENSION.mkv')
        norg = testapp.mock_source('2.Broke.Girls.S06E16.720p.HDTV.mkv')
        self.app.insert_sources(dimension, norg)
        self.app.mediainfo.process(dimension, norg)

        self.assertQuery(
            [dimension],
            release_group_in=['dimension', 'eztv'])

        self.assertQuery(
            [],
            release_group_in=['eztv'])

        self.assertQuery(
            [dimension],
            release_group='dImEnSiOn')

    def test_container(self):
        mkv = testapp.mock_source('2.Broke.Girls.S06E16.720p.HDTV.X264-DIMENSION.mkv')
        mp4 = testapp.mock_source('2.Broke.Girls.S06E16.720p.HDTV.mp4')
        mixed = testapp.mock_source('2.Broke.Girls.S06E16.720p.HDTV.X264-DIMENSION.mkv[eztv].avi')
        self.app.insert_sources(mkv, mp4, mixed)
        self.app.mediainfo.process(mkv, mp4, mixed)

        self.assertQuery(
            [mkv, mixed],
            container='mkv')

        self.assertQuery(
            [mkv, mp4, mixed],
            container_in=['mkv', 'mp4'])

        self.assertQuery(
            [],
            container='avi')  # Container for mixed is mkv NOT avi. Check dock for ContainerFilter


class EpisodeSelectorTest(SelectorTestCase):
    def setUp(self):
        self.app = testapp.TestApp({
            'plugins.filters.sourcefields.enabled': True,
            'plugins.filters.episodefields.enabled': True,
            'plugins.filters.mediainfo.enabled': True,
            'plugins.sorters.basic.enabled': True,
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
            type='episode', series='*')

        self.assertQuery(
            [srcs[0]],
            type='episode', series='game of thrones')

        srcs[0].state = models.State.DONE

        self.assertQuery(
            [srcs[2]],
            type='episode', series='*')

        self.assertQuery(
            [],
            type='episode', series='game of thrones')

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
            type='episode', series='game of thrones', quality='hdtv')

        # After this state change nothing matches
        for src in srcs:
            src.state = models.State.DONE
        self.assertQuery(
            [],
            type='episode', series='game of thrones', quality='hdtv')

        # Adding a new version from existings episode should be matched
        new_source = s('Game of Thrones S05E01 HDTV PROPER', type='episode')
        self.app.insert_sources(new_source,)
        self.assertQuery(
            [new_source],
            type='episode', series='game of thrones', quality='hdtv')

        # Revert src states and link episodes with sources
        for src in srcs:
            src.state = models.State.NONE
        query = self.app.selector.query_from_args(
            params=dict(type='episode', series='game of thrones', quality='hdtv'))
        matches = self.app.selector.matches(query)
        for src in self.app.selector.select_from_mixed_sources(matches):
            src.episode.selection = models.EpisodeSelection(source=src)

        # Check or queryspec again
        self.assertQuery(
            [],
            type='episode', series='game of thrones', quality='hdtv')

        # And with new sources?
        new_source = s('Game of Thrones S05E01 HDTV LoL x264', type='episode')
        self.app.insert_sources(new_source,)
        self.assertQuery(
            [],
            type='episode', series='game of thrones', quality='hdtv')

        # But… let's check with new episode
        new_source = s('Game of Thrones S05E04 HDTV LoL x264', type='episode')
        self.app.insert_sources(new_source,)
        self.assertQuery(
            [new_source],
            type='episode', series='game of thrones', quality='hdtv')

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
        app = testapp.TestApp({
            'plugins.filters.sourcefields.enabled': True,
            'plugins.filters.episodefields.enabled': True,
            'plugins.filters.mediainfo.enabled': True,
            'plugins.sorters.basic.enabled': True,
            'log-level': 'DEBUG'
        })

        app.insert_sources(*srcs)
        query = app.selector.query_from_args(
            params=dict(type='episode', series='true detective',
                        quality='720p', language='eng-us'))

        matches = list(app.selector.matches(query))
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
            'plugins.filters.sourcefields.enabled': True,
            'plugins.filters.episodefields.enabled': True,
            'plugins.filters.mediainfo.enabled': True,
            'plugins.sorters.basic.enabled': True,
        })

        app.insert_sources(*srcs)
        query = app.selector.query_from_args(
            params=dict(type='episode', series='the last man on earth'))

        matches = list(app.selector.matches(query))
        self.assertEqual(len(matches), 9)

        groups = self.app.selector.group(matches)
        self.assertEqual(len(groups), 3)


if __name__ == '__main__':
    unittest.main()
