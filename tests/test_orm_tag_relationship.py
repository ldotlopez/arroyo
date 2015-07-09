import unittest
import os


from ldotcommons.sqlalchemy import create_session
from sqlalchemy import exc
import tempfile


from arroyo import models


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
