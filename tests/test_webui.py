# -*- coding: utf-8 -*-

import unittest


import json


import testapp
from arroyo.plugins.webuicmd import webapp


def parse(response):
    try:
        return (json.loads(response.data.decode(response.charset)),
                response.status_code)
    except:
        print(repr(response))
        raise


class WebUITest(unittest.TestCase):
    def test_simple(self):
        app = testapp.TestApp({
            'plugin.webuicmd.enabled': True,
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
            resp, code = parse(cl.get("/api/search/?name-glob=*foo*"))
            self.assertEqual(code, 200, msg=resp)
            self.assertEqual(len(resp), 1)

    def test_settings_mngm(self):
        app = testapp.TestApp({
            'plugin.webuicmd.enabled': True,
        })

        webui = webapp.WebApp(app)
        with webui.test_client() as cl:
            # Get current config
            resp, code = parse(cl.get('/api/settings/'))
            self.assertTrue(
                resp['plugin']['webuicmd']['enabled']
            )

            # Change some value
            oldvalue = resp['auto-cron']
            resp['auto-cron'] = not oldvalue
            cl.post(
                '/api/settings/',
                data=json.dumps(resp),
                content_type='application/json')

            # Check new valie
            resp, code = parse(cl.get('/api/settings/'))
            self.assertTrue(
                resp['plugin']['webuicmd']['enabled'] != oldvalue
            )

if __name__ == '__main__':
    unittest.main()
