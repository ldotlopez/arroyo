# -*- coding: utf-8 -*-
# [SublimeLinter pep8-max-line-length:160 flake8-max-line-length:160]
# vim: set fileencoding=utf-8 :

import unittest

from arroyo import ngstore as store


class SelectorInterfaceTest(unittest.TestCase):
    def test_get_set(self):
        s = store.Store()

        s.set_('x', 1)
        self.assertEqual(s.get_('x'), 1)
        self.assertEqual(s.get_(None), {'x': 1})

    def test_delete(self):
        s = store.Store()

        s.set_('x', 1)
        s.delete_('x')
        with self.assertRaises(store.KeyNotFoundError) as cm:
            s.get_('x')
        self.assertEqual(cm.exception.args[0], 'x')

        self.assertEqual(s.get_(None), {})

    def test_get_with_default(self):
        s = store.Store()

        self.assertEqual(s.get_('foo', default=3), 3)
        self.assertEqual(s.get_('foo', default='x'), 'x')
        with self.assertRaises(store.KeyNotFoundError) as cm:
            s.get_('foo')
        self.assertEqual(cm.exception.args[0], 'foo')

        self.assertEqual(s.get_(None), {})

    def test_all_keys(self):
        s = store.Store()
        s.set_('x', 1)
        s.set_('y.a', 2)
        s.set_('y.b', 2)

        self.assertEqual(
            set(s.all_keys()),
            set(['x', 'y.a', 'y.b']))

    def test_has_key(self):
        s = store.Store()
        s.set_('x', 1)
        s.set_('y.a', 2)
        s.set_('y.b', 2)

        self.assertTrue(s.has_key_('x'))
        self.assertTrue(s.has_key_('y.a'))
        self.assertFalse(s.has_key_('y'))

    def test_has_ns(self):
        s = store.Store()
        s.set_('x', 1)
        s.set_('y.a', 2)
        s.set_('y.b', 2)

        self.assertFalse(s.has_namespace_('x'))
        self.assertFalse(s.has_namespace_('y.a'))
        self.assertTrue(s.has_namespace_('y'))
        self.assertFalse(s.has_namespace_('z'))

    def test_override(self):
        s = store.Store()
        s.set_('x', 1)
        s.set_('x', 'a')
        self.assertEqual(s.get_('x'), 'a')
        self.assertEqual(s.get_(None), {'x': 'a'})

    def test_override_with_dict(self):
        s = store.Store()
        s.set_('x', 1)
        s.set_('x', 'a')
        self.assertEqual(s.get_('x'), 'a')
        self.assertEqual(s.get_(None), {'x': 'a'})

    def test_key_not_found(self):
        s = store.Store()

        with self.assertRaises(store.KeyNotFoundError) as cm:
            s.get_('y')
        self.assertEqual(cm.exception.args[0], 'y')

        self.assertEqual(s.get_(None), {})

    def test_children(self):
        s = store.Store()
        s.set_('a.b.x', 1)
        s.set_('a.b.y', 2)
        s.set_('a.b.z', 3)
        s.set_('a.c.w', 4)

        self.assertEqual(
            set(s.children_('a.b')),
            set(['x', 'y', 'z']))

        self.assertEqual(
            set(s.children_('a')),
            set(['b', 'c']))

        self.assertEqual(
            s.children_(None),
            ['a'])

    def test_complex(self):
        s = store.Store()

        s.set_('a.b.c', 3)
        self.assertEqual(s.get_('a.b.c'), 3)
        self.assertEqual(s.get_('a.b'), {'c': 3})
        self.assertEqual(s.get_('a'), {'b': {'c': 3}})
        self.assertEqual(s.get_(None), {'a': {'b': {'c': 3}}})

        s.set_('a.k.a', 1)
        s.delete_('a.b')
        self.assertEqual(s.get_(None), {'a': {'k': {'a': 1}}})

        with self.assertRaises(store.KeyNotFoundError) as cm:
            s.get_('a.b')
        self.assertEqual(cm.exception.args[0], 'a.b')

    def test_validator_simple(self):
        def validator(k, v):
            if k == 'int' and not isinstance(v, int):
                raise store.ValidationError(k, v, 'not int')

            return v

        s = store.Store()
        s.add_validator_(validator)

        s.set_('int', 1)
        with self.assertRaises(store.ValidationError):
            s.set_('int', 'a')

    def test_validator_alters_value(self):
        def validator(k, v):
            if k == 'int' and not isinstance(v, int):
                try:
                    v = int(v)
                except ValueError:
                    raise store.ValidationError(k, v, 'not int')

            return v

        s = store.Store()
        s.add_validator_(validator)

        s.set_('int', 1.1)
        self.assertEqual(s.get_('int'), 1)
        with self.assertRaises(store.ValidationError):
            s.set_('int', 'a')

    def test_illegal_keys(self):
        s = store.Store()

        with self.assertRaises(store.IllegalKeyError):
            s.set_(1, 1)

        with self.assertRaises(store.IllegalKeyError):
            s.set_('.x', 1)

        with self.assertRaises(store.IllegalKeyError):
            s.set_('.x', 1)

        with self.assertRaises(store.IllegalKeyError):
            s.set_('x.', 1)

        with self.assertRaises(store.IllegalKeyError):
            s.set_('x..a', 1)

    def test_dottet_value(self):
        s = store.Store()
        s.set_('a.b', 'c.d')
        self.assertEqual(s.get_('a.b'), 'c.d')

if __name__ == '__main__':
    unittest.main()
