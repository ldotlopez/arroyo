import unittest


from ldotcommons.sqlalchemy import create_session
from sqlalchemy import exc


from arroyo import models


class SourceTagsTest(unittest.TestCase):
    def setUp(self):
        self.sess = create_session('sqlite:///:memory:')

    def test_adding(self):
        src = models.Source.from_data('src')
        tag1 = models.SourceTag(key='foo', value=1)
        tag2 = models.SourceTag(key='bar', value=2)

        src.tags.append(tag1)
        src.tags.append(tag2)
        self.sess.add(src)
        self.sess.commit()

        self.assertEqual(len(src.tags), 2)

    def test_orphan_tag(self):
        src = models.Source.from_data('src')
        tag1 = models.SourceTag(key='foo', value=1)
        tag2 = models.SourceTag(key='bar', value=2)

        src.tags.append(tag1)
        src.tags.append(tag2)
        src.tags.remove(tag2)
        self.sess.add(src)
        self.sess.commit()

        self.assertEqual(len(src.tags), 1, 'Source has more that one tag')
        self.assertEqual(self.sess.query(models.Source).count(), 1, 'Src model was deleted')
        self.assertEqual(self.sess.query(models.SourceTag).count(), 1, 'Tags was not deleted')

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
