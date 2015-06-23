# -*- coding: utf-8 -*-
# [SublimeLinter pep8-max-line-length:119]
# vim: set fileencoding=utf-8 :

import unittest

from itertools import count
import time

from arroyo import core
from arroyo.exts import CronTask


class TestZeroTask(CronTask):
    INTERVAL = 0

    def __init__(self, app):
        super().__init__(app)

    def run(self):
        i = getattr(self.app, 'zero', -1)
        setattr(self.app, 'zero', i + 1)


class TestMinuteTask(CronTask):
    INTERVAL = 60

    def __init__(self, app):
        super().__init__(app)
        self.g = count()

    def run(self):
        i = getattr(self.app, 'minute', -1)
        setattr(self.app, 'minute', i + 1)


class MissingIntervalTask(CronTask):
    pass


class CronTest(unittest.TestCase):

    def setUp(self):
        self.settings = core.build_basic_settings()
        self.settings.set('mediainfo', False)
        self.settings.set('log-level', 'CRITICAL')
        self.settings.set('db-uri', 'sqlite:///:memory:')
        self.app = core.Arroyo(self.settings)

    def test_discover(self):
        self.app.register('crontask', 'minute', TestMinuteTask)

        self.assertEqual(
            TestMinuteTask,
            self.app.get_implementations('crontask')['minute'])

        self.assertTrue(
            isinstance(self.app.get_extension('crontask', 'minute'),
                       TestMinuteTask))

        with self.assertRaises(KeyError):
            self.app.get_implementations('crontask')['foo']

    def test_run(self):
        self.app.register('crontask', 'zero', TestZeroTask)
        self.app.register('crontask', 'minute', TestMinuteTask)

        self.assertFalse(hasattr(self.app, 'minute'))
        self.app.cron.run_task('zero')
        self.app.cron.run_task('minute')
        self.assertEqual(getattr(self.app, 'zero', None), 0)
        self.assertEqual(getattr(self.app, 'minute', None), 0)

        time.sleep(1)
        self.app.cron.run_task('zero')
        self.app.cron.run_task('minute')
        self.assertEqual(getattr(self.app, 'zero', None), 1)
        self.assertEqual(getattr(self.app, 'minute', None), 0)

if __name__ == '__main__':
    unittest.main()
