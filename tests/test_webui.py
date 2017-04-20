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


import json


import testapp
from arroyo.plugins.webui import webapp


def parse(response):
    return (json.loads(response.data.decode(response.charset)),
            response.status_code)


class WebUITest(unittest.TestCase):
    def test_simple(self):
        app = testapp.TestApp({
            'plugin.webui.enabled': True,
            'plugin.sourcequery.enabled': True,
            'plugin.sourcefilters.enabled': True,
        })
        srcs = [
            testapp.mock_source('foo'),
            testapp.mock_source('bar'),
            testapp.mock_source('baz')
        ]
        app.insert_sources(*srcs)

        webui = webapp.WebApp(app)
        with webui.test_client() as cl:
            resp, code = parse(cl.get("/api/search?name-glob=*foo*"))
            self.assertEqual(code, 200, msg=resp)
            self.assertEqual(len(resp), 1)


if __name__ == '__main__':
    unittest.main()
