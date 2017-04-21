# -*- coding: utf-8 -*-

import contextlib
import time
import unittest


from arroyo import parallel


ARGS = range(8)
SQUARES = [x*x for x in ARGS]


# Core function
def cpu_bound_fn(item):
	time.sleep(0.1)
	return item * item


# Single shot version which can raise exceptions
def cpu_bound_fn_with_exception(item):
	if item % 2 == 0:
		return cpu_bound_fn(item)
	else:
		raise ValueError(item)


# Safe single shot version
def cpu_bound_fn_safe(item):
	return parallel.exception_catcher_helper(
		cpu_bound_fn_with_exception,
		item)


# Bulk core function
def cpu_bound_fn_bulk(*items):
	return parallel.bulk_helper(cpu_bound_fn, *items)


# Bulk version which can raise exceptions
def cpu_bound_fn_bulk_with_exceptions(*items):
	return parallel.bulk_helper(cpu_bound_fn_with_exception, *items)


# Safe bulk version
def cpu_bound_fn_bulk_safe(*items):
	return parallel.bulk_helper(cpu_bound_fn_safe, *items)


class ParallelTest(unittest.TestCase):
	def test_basic(self):
		results = parallel.cpu_map(cpu_bound_fn, ARGS)
		self.assertEqual(results, SQUARES)

	def test_basic_raises_exceptions(self):
		with self.assertRaises(ValueError) as cm:
			results = parallel.cpu_map(cpu_bound_fn_with_exception, ARGS)

	def test_basic_safe(self):
		results = parallel.cpu_map(cpu_bound_fn_safe, ARGS)

		for (idx, res) in enumerate(results):
			if idx % 2 == 0:
				self.assertEqual(res, SQUARES[idx])
			else:
				self.assertTrue(isinstance(res, ValueError))

	def test_bulk(self):
		results = parallel.cpu_map(cpu_bound_fn_bulk, ARGS, bulk=True)
		self.assertEqual(results, SQUARES)

	def test_bulk_raises_exceptions(self):
		with self.assertRaises(ValueError) as cm:
			results = parallel.cpu_map(cpu_bound_fn_bulk_with_exceptions, ARGS, bulk=True)

	def test_bulk_safe(self):
		results = parallel.cpu_map(cpu_bound_fn_bulk_safe, ARGS, bulk=True)

		for (idx, res) in enumerate(results):
			if idx % 2 == 0:
				self.assertEqual(res, SQUARES[idx])
			else:
				self.assertTrue(isinstance(res, ValueError))


class SingleProcessParallelTest(ParallelTest):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self._orig_cpu_parallelize = parallel.cpu_map

	def setUp(self):
		setattr(parallel, 'cpu_parallelize', self.cpu_parallelize)
		
	def tearDown(self):
		setattr(parallel, 'cpu_parallelize', self._orig_cpu_parallelize)

	def cpu_parallelize(self, *args, **kwargs):
		return self._orig_cpu_parallelize(*args, **kwargs, n_cpus=1)


if __name__ == '__main__':
	unittest.main()