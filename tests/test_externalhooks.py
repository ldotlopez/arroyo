# -*- coding: utf-8 -*-
# [SublimeLinter pep8-max-line-length:160 flake8-max-line-length:160]
# vim: set fileencoding=utf-8 :

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
        backend._update_info(src, {'location': '/foo/bar'})
        backend._update_state(src, models.Source.State.DONE)

        self.app.downloads.sync()

if __name__ == '__main__':
    unittest.main()
