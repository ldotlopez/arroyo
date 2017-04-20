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

import testapp
from arroyo import models


class ExternalHooksTest(unittest.TestCase):
    def setUp(self):
        settings = {
            'log-level': 'DEBUG',
            'plugins.downloaders.mock.enabled': True,
            'plugins.misc.externalhooks.enabled': True,
            'plugins.misc.externalhooks.on-done': '/usr/bin/env'
        }
        self.app = testapp.TestApp(settings)

    def test_base(self):
        src = testapp.mock_source('foo')
        self.app.insert_sources(src)
        self.app.downloads.add(src)

        backend = self.app.downloads.backend
        backend._update_info(src, {
            'location': '/foo/bar'
        })
        backend._update_state(src, models.State.DONE)
        self.app.downloads.sync()

if __name__ == '__main__':
    unittest.main()
