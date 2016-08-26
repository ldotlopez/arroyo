import unittest
import os
import sys

from ldotcommons import utils
from ldotcommons.sqlalchemy import create_session
from sqlalchemy import exc
import tempfile

from testapp import mock_source

from arroyo import models


class SourceModelTest(unittest.TestCase):
    def setUp(self):
        self.sess = create_session('sqlite:///:memory:')

    def tearDown(self):
        delattr(self, 'sess')

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

        self.sess.add(src_with_urn)
        self.sess.add(src_without_urn)
        self.sess.commit()

        q = self.sess.query(models.Source)

        # Check as attribute
        self.assertTrue(
            all([isinstance(x, models.Source) for x in q.all()])
        )

        # Check as expression
        res1 = set(
            q
            .filter(models.Source._discriminator.startswith('urn'))
            .all())
        self.assertEqual(res1, set([src_with_urn]))

        res2 = set(
            q
            .filter(models.Source._discriminator.startswith('http:'))
            .all())
        self.assertEqual(res2, set([src_without_urn]))

    def test_entity(self):
        ep1 = models.Episode(series='series1', season=1, number=1)
        ep2 = models.Episode(series='series2', season=1, number=1)
        mov1 = models.Movie(title='movie1')

        src1 = mock_source(name='src_ep1', episode=ep1)
        src2 = mock_source(name='src_ep2')
        src3 = mock_source(name='src_mov1')
        src2.episode = ep2
        src3.movie = mov1

        for x in [src1, src2, src3]:
            self.sess.add(x)
        self.sess.commit()

        q = self.sess.query(models.Source)

        # Check as attribute
        self.assertEqual(
            set([x.entity for x in q.all()]),
            set([ep1, ep2, mov1])
        )

        # Check as expression
        self.assertEqual(
            set(q.filter(models.Source.entity == ep2).all()),
            set([src2])
        )

        # # Not supported by sqlalchemy
        # self.assertEqual(
        #     set(self.sess.query(models.Source)
        #         .filter(models.Source.entity.in_([ep1, mov1]))
        #         .all()),
        #     set([src1, src3])
        # )

    def test_age(self):
        t1 = utils.now_timestamp() - 10
        t2 = utils.now_timestamp()

        s1 = mock_source(name='s1', created=t1, last_seen=t1)
        s2 = mock_source(name='s2', created=t2, last_seen=t2)

        for x in [s1, s2]:
            self.sess.add(x)
        self.sess.commit()

        # Check if models.Source.age produces different values for different
        # models
        res = set(
            self.sess.query(models.Source).
            filter(models.Source.age < 5).
            all()
        )
        self.assertEqual(res, set([s2]))

        res = set(
            self.sess.query(models.Source).
            filter(models.Source.age > 5).
            all()
        )
        self.assertEqual(res, set([s1]))

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
        s3 = mock_source(name='s2')

        self.sess.add(s1)
        self.sess.add(s2)
        self.sess.add(s3)
        self.sess.commit()

        q = self.sess.query(models.Source)
        res = q.all()

        # Check as attribute
        self.assertTrue(all(
            [isinstance(x.share_ratio, (float, type(None))) for x in res]
        ))

        # Check as expression
        self.assertEqual(
            set(q.filter(models.Source.share_ratio > 1).all()),
            set([s1])
        )
        self.assertEqual(
            set(q.filter(models.Source.share_ratio < 1).all()),
            set([s2])
        )

    def test_language(self):
        s1 = mock_source(name='s1', language='xxx-xx')

        with self.assertRaises(ValueError):
            s2 = mock_source(name='s1', language='spanish')

        with self.assertRaises(ValueError):
            s2 = mock_source(name='s1', language=object())

    def test_type(self):
        s1 = mock_source(name='s1', type='movie')

        with self.assertRaises(ValueError):
            s2 = mock_source(name='s1', type='foo')

        with self.assertRaises(ValueError):
            s2 = mock_source(name='s1', type=object())

    def test_as_dict(self):
        s = mock_source(name='foo')
        s.tags.append(models.SourceTag(key='a', value='b'))

        d = s.as_dict()
        self.assertTrue(isinstance(d['tags'], dict))
        self.assertTrue('tag_dict' not in d)


class SourceTagsTest(unittest.TestCase):
    def setUp(self):
        self.path = tempfile.mktemp()
        self.sess = create_session('sqlite:///'+self.path)

    def tearDown(self):
        os.unlink(self.path)

    def test_adding(self):
        src = models.Source.from_data('src')
        tag1 = models.SourceTag(key='foo', value=1)
        tag2 = models.SourceTag(key='bar', value=2)

        src.tags.append(tag1)
        src.tags.append(tag2)
        self.sess.add(src)
        self.sess.commit()

        self.assertEqual(src.tags.count(), 2)

    def test_orphan_tag(self):
        src = models.Source.from_data('src')
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
        src = models.Source.from_data('src')
        tag1 = models.SourceTag(key='foo', value=1)
        tag2 = models.SourceTag(key='bar', value=2)

        src.tags.append(tag1)
        src.tags.append(tag2)
        self.sess.add(src)
        with self.assertRaises(exc.InvalidRequestError):
            self.sess.delete(tag2)

    def test_delete_source(self):
        src1 = models.Source.from_data('src1')
        src2 = models.Source.from_data('src2')
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
        src1 = models.Source.from_data('src1')
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
        src1 = models.Source.from_data('src1')
        tag1 = models.SourceTag('foo', 'a')
        tag2 = models.SourceTag('foo', 'b')

        src1.tags.append(tag1)
        src1.tags.append(tag2)

        self.sess.add(src1)
        with self.assertRaises(exc.IntegrityError):
            self.sess.commit()

if __name__ == '__main__':
    unittest.main()
