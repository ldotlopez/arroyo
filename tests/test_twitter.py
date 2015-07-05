import unittest


from arroyo import models
from testapp import TestApp, mock_source


from ldotcommons.messaging import twitter as ldottwitter


class TwitterTest(unittest.TestCase):
    def setUp(self):
        self.app = TestApp({
            'extensions.services.twitter.enabled': True,
            'extensions.services.twitter.consumer-key': 'x',
            'extensions.services.twitter.consumer-secret': 'x',
            'extensions.services.twitter.token': 'x',
            'extensions.services.twitter.token-secret': 'x',
            'extensions.services.twitter.notify-on': 'source-state-change=done'
        })

    def test_raw_state_change(self):
        send_msg = ''

        def fake_send(self, msg):
            nonlocal send_msg
            send_msg = msg

        foo = mock_source('Foo')
        self.app.insert_sources(foo)

        foo.state = models.Source.State.DONE

        with self.app.hijack(ldottwitter.Twitter, 'send', fake_send):
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
                models.Source.State.DONE)
            self.app.downloads.sync()
            self.assertEqual(send_msg, '[Arroyo] Foo is done')

    def test_state_change_without_notification(self):
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
                models.Source.State.ARCHIVED)
            self.app.downloads.sync()
            self.assertEqual(send_msg, '')


if __name__ == '__main__':
    unittest.main()
