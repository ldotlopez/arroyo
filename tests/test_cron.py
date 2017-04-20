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

import itertools
import time


from arroyo import cron, plugin
import testapp


class NoopCommand(plugin.Command):
    __extension_name__ = 'noop'

    def run(self, arguments):
        pass


class TestZeroTask(plugin.CronTask):
    __extension_name__ = 'zero'
    INTERVAL = 0

    def __init__(self, app):
        super().__init__(app)

    def run(self):
        i = getattr(self.app, 'zero', -1)
        setattr(self.app, 'zero', i + 1)
        super().run()


class TestMinuteTask(plugin.CronTask):
    __extension_name__ = 'minute'
    INTERVAL = 60

    def __init__(self, app):
        super().__init__(app)
        self.g = itertools.count()

    def run(self):
        i = getattr(self.app, 'minute', -1)
        setattr(self.app, 'minute', i + 1)
        super().run()


class MissingIntervalTask(plugin.CronTask):
    __extension_name__ = 'missing'


class CronTest(unittest.TestCase):

    def setUp(self):
        self.app = testapp.TestApp()

    def test_discover(self):
        self.app.register_extension_class(TestMinuteTask)

        self.assertEqual(
            TestMinuteTask,
            self.app.get_implementations(cron.CronTask)['minute'])

        self.assertTrue(
            isinstance(self.app.get_extension(cron.CronTask, 'minute'),
                       TestMinuteTask))

        with self.assertRaises(KeyError):
            self.app.get_implementations(cron.CronTask)['foo']

    def test_run(self):
        self.app.register_extension_class(TestZeroTask)
        self.app.register_extension_class(TestMinuteTask)

        self.assertFalse(hasattr(self.app, 'minute'))
        self.app.cron.run_by_name('zero')
        self.app.cron.run_by_name('minute')
        self.assertEqual(getattr(self.app, 'zero', None), 0)
        self.assertEqual(getattr(self.app, 'minute', None), 0)

        time.sleep(1)
        self.app.cron.run_by_name('zero')
        self.app.cron.run_by_name('minute')
        self.assertEqual(getattr(self.app, 'zero', None), 1)
        self.assertEqual(getattr(self.app, 'minute', None), 0)

    def test_force_run(self):
        self.app.register_extension_class(TestMinuteTask)

        self.assertFalse(hasattr(self.app, 'minute'))

        self.app.cron.run_by_name('minute')
        self.assertEqual(getattr(self.app, 'minute', None), 0)

        self.app.cron.run_by_name('minute', force=True)
        self.assertEqual(getattr(self.app, 'minute', None), 1)


if __name__ == '__main__':
    unittest.main()
