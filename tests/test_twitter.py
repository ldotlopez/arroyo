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


from arroyo import models
from testapp import TestApp, mock_source


from appkit.messaging import twitter as appkit_twitter


class TwitterTest(unittest.TestCase):
    def setUp(self):
        self.app = TestApp({
            'plugin.mockdownloader.enabled': True,
            'plugin.twitter.enabled': True,
            'plugin.twitter.consumer-key': 'x',
            'plugin.twitter.consumer-secret': 'x',
            'plugin.twitter.token': 'x',
            'plugin.twitter.token-secret': 'x',
            'plugin.twitter.notify-on': 'source-state-change=done'
        })

    def test_raw_state_change(self):
        send_msg = ''

        def fake_send(self, msg):
            nonlocal send_msg
            send_msg = msg

        foo = mock_source('Foo')
        self.app.insert_sources(foo)

        foo.state = models.State.DONE

        with self.app.hijack(appkit_twitter.Twitter, 'send', fake_send):
            self.app.signals.send('source-state-change', source=foo)
            self.assertEqual(send_msg, '[Arroyo] Foo is done')

    def test_state_change(self):
        send_msg = ''

        def fake_send(self, msg):
            nonlocal send_msg
            send_msg = msg

        foo = mock_source('Foo')
        self.app.insert_sources(foo)

        with self.app.hijack(ldottwitter.Twitter, 'send', fake_send):
            self.app.downloads.add(foo)
            self.app.downloads.backend._update_state(
                foo,
                models.State.DONE)
            self.app.downloads.sync()
            self.assertEqual(send_msg, '[Arroyo] Foo is done')

    def test_state_change_without_notification(self):
        send_msg = ''

        def fake_send(self, msg):
            nonlocal send_msg
            send_msg = msg

        foo = mock_source('Foo')
        self.app.insert_sources(foo)

        with self.app.hijack(appkit_twitter.Twitter, 'send', fake_send):
            self.app.downloads.add(foo)
            self.app.downloads.backend._update_state(
                foo,
                models.State.ARCHIVED)
            self.app.downloads.sync()
            self.assertEqual(send_msg, '')


if __name__ == '__main__':
    unittest.main()
