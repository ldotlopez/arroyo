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

import sqlalchemy as sa
from sqlalchemy import orm
from appkit.db import sqlalchemyutils as sautils

# Base = declarative.declarative_base()
# Base.metadata.naming_convention = {
#     "ix": 'ix_%(column_0_label)s',
#     "uq": "uq_%(table_name)s_%(column_0_name)s",
#     "ck": "ck_%(table_name)s_%(constraint_name)s",
#     "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
#     "pk": "pk_%(table_name)s"
# }

from arroyo.models import Source, SourceTag


def mock_source(name, **kwargs):
    kwargs['provider'] = 'mock'
    kwargs['uri'] = 'mock://' + name
    kwargs['name'] = name
    return Source(**kwargs)


def l(tags):
    if isinstance(tags, list):
        return tags
    else:
        return tags.all()


class Testmock_sourceAndSourceTagRelationship(unittest.TestCase):
    def assertQueryResult(self, qs, expected):
        if not isinstance(expected, list):
            expected = expected.all()

        return self.assertEqual(qs.all(), expected)

    def setUp(self):
        engine = sa.create_engine('sqlite:///:memory:', echo=False)
        sautils.Base.metadata.create_all(engine)
        sm = orm.sessionmaker(bind=engine)
        self.sess = sm()

    def test_simple(self):
        s1 = mock_source(name='foo')
        s1.tags = [SourceTag(key='a', value='aa')]
        self.sess.add(s1)
        self.sess.commit()
        self.assertQueryResult(
            self.sess.query(Source),
            [s1]
        )
        self.assertQueryResult(
            self.sess.query(SourceTag),
            s1.tags
        )

    def test_delete_source(self):
        # Check source->tag cascade
        s1 = mock_source(name='s1', tags=[SourceTag(key='foo', value='bar')])
        self.sess.add(s1)
        self.sess.commit()

        self.assertQueryResult(
            self.sess.query(SourceTag),
            s1.tags
        )
        self.sess.delete(s1)
        self.sess.commit()

        self.assertQueryResult(
            self.sess.query(SourceTag),
            [])
        self.assertQueryResult(
            self.sess.query(Source),
            [])

    def test_delete_tags(self):
        # Check NO tag->source cascade
        s1 = mock_source(name='s1', tags=[SourceTag(key='foo', value='bar')])
        self.sess.add(s1)
        self.sess.commit()

        self.assertQueryResult(
            self.sess.query(SourceTag),
            s1.tags)

        s1.tags = []
        self.sess.commit()

        self.assertEqual(
            self.sess.query(SourceTag).all(),
            [])
        self.assertEqual(
            self.sess.query(Source).all(),
            [s1])

    def test_uniqueness(self):
        s1 = mock_source(name='s1', tags=[SourceTag(key='foo', value='bar')])
        self.sess.add(s1)
        self.sess.commit()

        s2 = mock_source(name='s1')
        self.sess.add(s2)
        with self.assertRaises(sa.exc.IntegrityError):
            self.sess.commit()
        self.sess.rollback()

    def test_merge(self):
        s1 = mock_source(name='s1',
                         tags=[SourceTag(key='foo', value='bar')])
        self.sess.add(s1)
        self.sess.commit()

        s2 = mock_source(name='s1',
                         tags=[SourceTag(key='foo-alt', value='bar-alt')])

        s1.tags = s2.tags
        self.sess.expunge(s2)
        self.sess.add_all(s1.tags)

        # This method works with dynamic
        # tags = s2.tags.all()
        # for x in s1.tags:
        #     s1.tags.remove(x)
        # for x in s2.tags:
        #     s2.tags.remove(x)
        # for x in tags:
        #     s1.tags.append(x)

        self.sess.commit()
        self.assertTrue(
            self.sess.query(Source).one().tags[0].key == 'foo-alt')


if __name__ == '__main__':
    unittest.main()
