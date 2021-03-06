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
import os
import sys

from appkit import utils
from appkit.db import sqlalchemyutils as sautils
from sqlalchemy import exc
import tempfile

from testapp import mock_source

from arroyo import models


class SourceModelTest(unittest.TestCase):
    def setUp(self):
        self.sess = sautils.create_session('sqlite:///:memory:')
        self.srcquery = self.sess.query(models.Source)

    def tearDown(self):
        delattr(self, 'sess')
        delattr(self, 'srcquery')

    def assertEqualSetAndLen(self, a, b):
        self.assertEqual(set(a), set(b))
        self.assertEqual(len(a), len(b))

    def test_discriminator(self):
        src_with_urn = mock_source(
            name='s1',
            urn='urn:btih:0000000000000000000000000000000000000001',
            uri='magnet:?xt=urn:btih:0000000000000000000000000000000000000001'
        )

        src_without_urn = mock_source(
            name='s2',
            urn=None,
            uri='http://i-am-a-lazy-source.org/'
        )

        self.sess.add_all([src_with_urn, src_without_urn])
        self.sess.commit()

        # Check as attribute

        self.assertEqualSetAndLen(
            ['urn:btih:0000000000000000000000000000000000000001',
             'http://i-am-a-lazy-source.org/'],
            [x._discriminator for x in self.srcquery.all()]
        )

        # Check as expression

        self.assertEqualSetAndLen(
            [src_with_urn],
            self.srcquery
                .filter(models.Source._discriminator.startswith('urn'))
                .all()
        )

        self.assertEqualSetAndLen(
            [src_without_urn],
            self.srcquery
                .filter(models.Source._discriminator.startswith('http'))
                .all()
        )

    def test_needs_postprocessing(self):
        src1 = mock_source(name='src1', urn=None, uri='foo://')
        src2 = mock_source(
            name='src2',
            urn='urn:btih:0000000000000000000000000000000000000001',
            uri='magnet:?xt=urn:btih:0000000000000000000000000000000000000001'
        )

        self.sess.add_all([src1, src2])
        self.sess.commit()

        # As property

        self.assertEqualSetAndLen(
            [src1],
            [x for x in self.srcquery.all()
             if x.needs_postprocessing]
        )

        # As expression

        self.assertEqualSetAndLen(
            [src1],
            self.srcquery
                .filter(models.Source.needs_postprocessing == True)  # nopep8
                .all()
        )

        self.assertEqualSetAndLen(
            [src2],
            self.srcquery
                .filter(models.Source.needs_postprocessing == False)  # nopep8
                .all()
        )

        self.assertEqualSetAndLen(
            [src1],
            self.srcquery
                .filter(models.Source.needs_postprocessing)
                .all()
        )

        self.assertEqualSetAndLen(
            [src2],
            self.srcquery
                .filter(~models.Source.needs_postprocessing)
                .all()
        )

    def test_entity(self):
        ep1 = models.Episode(series='series1', season=1, number=1)
        ep2 = models.Episode(series='series2', season=1, number=1)
        mov1 = models.Movie(title='movie1')

        src1 = mock_source(name='src_ep1', episode=ep1)
        src2 = mock_source(name='src_ep2')
        src3 = mock_source(name='src_mov1')
        src2.episode = ep2
        src3.movie = mov1

        self.sess.add_all([src1, src2, src3])
        self.sess.commit()

        # Check as attribute
        self.assertEqualSetAndLen(
            [ep1, ep2, mov1],
            [x.entity for x in self.srcquery.all()]
        )

        # Check as expression
        self.assertEqualSetAndLen(
            [src2],
            self.srcquery.filter(models.Source.entity == ep2).all()
        )

        # # Not supported by sqlalchemy
        # self.assertEqual(
        #     set(self.sess.query(models.Source)
        #         .filter(models.Source.entity.in_([ep1, mov1]))
        #         .all()),
        #     set([src1, src3])
        # )

    def test_age(self):
        now = utils.now_timestamp()

        t1 = now - 10
        t2 = now

        s1 = mock_source(name='s1', created=t1, last_seen=t1)
        s2 = mock_source(name='s2', created=t2, last_seen=t2)

        self.sess.add_all([s1, s2])
        self.sess.commit()

        self.assertEqualSetAndLen(
            [0, 10],
            [x.age for x in self.srcquery.all()]
        )

        self.assertEqualSetAndLen(
            [s2],
            self.srcquery.filter(models.Source.age < 5).all()
        )

        self.assertEqualSetAndLen(
            [s1],
            self.srcquery.filter(models.Source.age > 5).all()
        )

    def test_share_ratio(self):
        s = mock_source(name='s', seeds=10, leechers=1)
        self.assertEqual(s.share_ratio, 10 / 1)

        s = mock_source(name='s', seeds=1, leechers=10)
        self.assertEqual(s.share_ratio, 1 / 10)

        s = mock_source(name='s', seeds=10)
        self.assertEqual(s.share_ratio, float(sys.maxsize))

        s = mock_source(name='s', seeds=10, leechers=0)
        self.assertEqual(s.share_ratio, float(sys.maxsize))

        s = mock_source(name='s', leechers=10)
        self.assertEqual(s.share_ratio, 0.0)

        s = mock_source(name='s', seeds=0, leechers=10)
        self.assertEqual(s.share_ratio, 0.0)

        s = mock_source(name='s', seeds=0, leechers=0)
        self.assertEqual(s.share_ratio, None)

        s = mock_source(name='s')
        self.assertEqual(s.share_ratio, None)

        s1 = mock_source(name='s1', seeds=10, leechers=1)
        s2 = mock_source(name='s2', seeds=1, leechers=10)
        s3 = mock_source(name='s3')

        self.sess.add_all([s1, s2, s3])
        self.sess.commit()

        q = self.sess.query(models.Source)
        res = q.all()

        # Check as attribute
        self.assertTrue(all(
            [isinstance(x.share_ratio, (float, type(None))) for x in res]
        ))

        # Check as expression
        self.assertEqualSetAndLen(
            [s1],
            self.srcquery.filter(models.Source.share_ratio > 1).all()
        )

        self.assertEqualSetAndLen(
            [s2],
            self.srcquery.filter(models.Source.share_ratio < 1).all()
        )

    def test_language(self):
        mock_source(name='s1', language='xxx-xx')

        with self.assertRaises(ValueError):
            mock_source(name='s1', language='spanish')

        with self.assertRaises(ValueError):
            mock_source(name='s1', language=object())

    def test_type(self):
        mock_source(name='s1', type='movie')

        with self.assertRaises(ValueError):
            mock_source(name='s1', type='foo')

        with self.assertRaises(ValueError):
            mock_source(name='s1', type=object())

    def test_asdict(self):
        s = mock_source(name='foo')
        s.tags.append(models.SourceTag(key='a', value='b'))

        d = s.asdict()
        self.assertTrue(isinstance(d['tags'], dict))
        self.assertTrue('tag_dict' not in d)


class SourceTagsRelationshipsTest(unittest.TestCase):
    def setUp(self):
        self.path = tempfile.mktemp()
        self.sess = sautils.create_session('sqlite:///'+self.path)

    def tearDown(self):
        os.unlink(self.path)

    def test_adding(self):
        src = mock_source('src')
        tag1 = models.SourceTag(key='foo', value=1)
        tag2 = models.SourceTag(key='bar', value=2)

        src.tags.append(tag1)
        src.tags.append(tag2)
        self.sess.add(src)
        self.sess.commit()

        self.assertEqual(src.tags.count(), 2)

    def test_orphan_tag(self):
        src = mock_source('src')
        tag1 = models.SourceTag(key='foo', value=1)
        tag2 = models.SourceTag(key='bar', value=2)

        src.tags.append(tag1)
        src.tags.append(tag2)
        src.tags.remove(tag2)
        self.sess.add(src)
        self.sess.commit()

        self.assertEqual(src.tags.count(), 1)
        self.assertEqual(self.sess.query(models.Source).count(), 1)
        self.assertEqual(self.sess.query(models.SourceTag).count(), 1)

    def test_delete_tag(self):
        src = mock_source('src')
        tag1 = models.SourceTag(key='foo', value=1)
        tag2 = models.SourceTag(key='bar', value=2)

        src.tags.append(tag1)
        src.tags.append(tag2)
        self.sess.add(src)
        with self.assertRaises(exc.InvalidRequestError):
            self.sess.delete(tag2)

    def test_delete_source(self):
        src1 = mock_source('src1')
        src2 = mock_source('src2')
        src1.tags.append(models.SourceTag('foo', '1'))
        src2.tags.append(models.SourceTag('bar', '1'))

        self.sess.add(src1)
        self.sess.add(src2)
        self.sess.commit()

        self.assertEqual(self.sess.query(models.Source).count(), 2)
        self.assertEqual(self.sess.query(models.SourceTag).count(), 2)

        self.sess.delete(src1)
        self.sess.commit()

        self.assertEqual(self.sess.query(models.Source).count(), 1)
        self.assertEqual(self.sess.query(models.SourceTag).count(), 1)

    def test_bulk_delete_source(self):
        src1 = mock_source('src1')
        tag1 = models.SourceTag(key='foo', value=1)
        tag2 = models.SourceTag(key='bar', value=2)
        src1.tags.append(tag1)
        src1.tags.append(tag2)
        self.sess.add(src1)
        self.sess.add(tag1)
        self.sess.add(tag1)
        self.sess.commit()

        self.sess.query(models.Source).delete()

    def test_duplicate_tag(self):
        src1 = mock_source('src1')
        tag1 = models.SourceTag('foo', 'a')
        tag2 = models.SourceTag('foo', 'b')

        src1.tags.append(tag1)
        src1.tags.append(tag2)

        self.sess.add(src1)
        with self.assertRaises(exc.IntegrityError):
            self.sess.commit()

if __name__ == '__main__':
    unittest.main()
