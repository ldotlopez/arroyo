# -*- coding: utf-8 -*-
# [SublimeLinter pep8-max-line-length:160 flake8-max-line-length:160]
# vim: set fileencoding=utf-8 :

import unittest

from arroyo import ngstore as store


class SelectorInterfaceTest(unittest.TestCase):
    def test_get_set(self):
        s = store.Store()

        s.set('x', 1)
        self.assertEqual(s.get('x'), 1)
        self.assertEqual(s.get(None), {'x': 1})

    def test_delete(self):
        s = store.Store()

        s.set('x', 1)
        s.delete('x')
        with self.assertRaises(store.KeyNotFoundError) as cm:
            s.get('x')
        self.assertEqual(cm.exception.args[0], 'x')

        self.assertEqual(s.get(None), {})

    def test_get_with_default(self):
        s = store.Store()

        self.assertEqual(s.get('foo', default=3), 3)
        self.assertEqual(s.get('foo', default='x'), 'x')
        with self.assertRaises(store.KeyNotFoundError) as cm:
            s.get('foo')
        self.assertEqual(cm.exception.args[0], 'foo')

        self.assertEqual(s.get(None), {})

    def test_override(self):
        s = store.Store()
        s.set('x', 1)
        s.set('x', 'a')
        self.assertEqual(s.get('x'), 'a')
        self.assertEqual(s.get(None), {'x': 'a'})

    def test_override_with_dict(self):
        s = store.Store()
        s.set('x', 1)
        s.set('x', 'a')
        self.assertEqual(s.get('x'), 'a')
        self.assertEqual(s.get(None), {'x': 'a'})

    def test_key_not_found(self):
        s = store.Store()

        with self.assertRaises(store.KeyNotFoundError) as cm:
            s.get('y')
        self.assertEqual(cm.exception.args[0], 'y')

        self.assertEqual(s.get(None), {})

    def test_children(self):
        s = store.Store()
        s.set('a.b.x', 1)
        s.set('a.b.y', 2)
        s.set('a.b.z', 3)
        s.set('a.c.w', 4)

        self.assertEqual(
            set(s.children('a.b')),
            set(['x', 'y', 'z']))

        self.assertEqual(
            set(s.children('a')),
            set(['b', 'c']))

        self.assertEqual(
            s.children(None),
            ['a'])

    def test_complex(self):
        s = store.Store()

        s.set('a.b.c', 3)
        self.assertEqual(s.get('a.b.c'), 3)
        self.assertEqual(s.get('a.b'), {'c': 3})
        self.assertEqual(s.get('a'), {'b': {'c': 3}})
        self.assertEqual(s.get(None), {'a': {'b': {'c': 3}}})

        s.set('a.k.a', 1)
        s.delete('a.b')
        self.assertEqual(s.get(None), {'a': {'k': {'a': 1}}})

        with self.assertRaises(store.KeyNotFoundError) as cm:
            s.get('a.b')
        self.assertEqual(cm.exception.args[0], 'a.b')

    def test_validator_simple(self):
        def validator(k, v):
            if k == 'int' and not isinstance(v, int):
                raise store.ValidationError(k, v, 'not int')

            return v

        s = store.Store()
        s.add_validator(validator)

        s.set('int', 1)
        with self.assertRaises(store.ValidationError):
            s.set('int', 'a')

    def test_validator_alters_value(self):
        def validator(k, v):
            if k == 'int' and not isinstance(v, int):
                try:
                    v = int(v)
                except ValueError:
                    raise store.ValidationError(k, v, 'not int')

            return v

        s = store.Store()
        s.add_validator(validator)

        s.set('int', 1.1)
        self.assertEqual(s.get('int'), 1)
        with self.assertRaises(store.ValidationError):
            s.set('int', 'a')

    def test_illegal_keys(self):
        s = store.Store()

        with self.assertRaises(store.IllegalKeyError):
            s.set(1, 1)

        with self.assertRaises(store.IllegalKeyError):
            s.set('.x', 1)

        with self.assertRaises(store.IllegalKeyError):
            s.set('.x', 1)

        with self.assertRaises(store.IllegalKeyError):
            s.set('x.', 1)

        with self.assertRaises(store.IllegalKeyError):
            s.set('x..a', 1)

    def test_dottet_value(self):
        s = store.Store()
        s.set('a.b', 'c.d')
        self.assertEqual(s.get('a.b'), 'c.d')

if __name__ == '__main__':
    unittest.main()
