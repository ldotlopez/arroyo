# -*- coding: utf-8 -*-
# [SublimeLinter pep8-max-line-length:119]
# vim: set fileencoding=utf-8 :

import unittest

import itertools
import time


from arroyo import exts
import testapp


class NoopCommand(exts.Command):
    def run(self, arguments):
        pass


class TestZeroTask(exts.CronTask):
    NAME = 'zero'
    INTERVAL = 0

    def __init__(self, app):
        super().__init__(app)

    def run(self):
        i = getattr(self.app, 'zero', -1)
        setattr(self.app, 'zero', i + 1)
        super().run()


class TestMinuteTask(exts.CronTask):
    NAME = 'minute'
    INTERVAL = 60

    def __init__(self, app):
        super().__init__(app)
        self.g = itertools.count()

    def run(self):
        i = getattr(self.app, 'minute', -1)
        setattr(self.app, 'minute', i + 1)
        super().run()


class MissingIntervalTask(exts.CronTask):
    pass


class CronTest(unittest.TestCase):

    def setUp(self):
        self.app = testapp.TestApp()

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
        self.app.cron.run('zero')
        self.app.cron.run('minute')
        self.assertEqual(getattr(self.app, 'zero', None), 0)
        self.assertEqual(getattr(self.app, 'minute', None), 0)

        time.sleep(1)
        self.app.cron.run('zero')
        self.app.cron.run('minute')
        self.assertEqual(getattr(self.app, 'zero', None), 1)
        self.assertEqual(getattr(self.app, 'minute', None), 0)

    def test_force_run(self):
        self.app.register('crontask', 'minute', TestMinuteTask)

        self.assertFalse(hasattr(self.app, 'minute'))

        self.app.cron.run('minute')
        self.assertEqual(getattr(self.app, 'minute', None), 0)

        self.app.cron.run('minute', force=True)
        self.assertEqual(getattr(self.app, 'minute', None), 1)

    # def test_auto_cron(self):
    #     app = testapp.TestApp({
    #         'auto-cron': True
    #     })
    #     app.register('crontask', 'zero', TestZeroTask)
    #     app.register('command', 'noop', NoopCommand)

    #     self.assertFalse(hasattr(self.app, 'zero'))
    #     app.run_from_args(['noop'])
    #     self.assertEqual(getattr(self.app, 'zero', None), 0)


if __name__ == '__main__':
    unittest.main()
