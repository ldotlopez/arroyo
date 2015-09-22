# -*- coding: utf-8 -*-

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
