# -*- coding: utf-8 -*-

from arroyo import pluginlib


import pprint


from appkit import messaging
from appkit.messaging import twitter as ldottwitter
import twitter


SETTINGS_NS = "plugin.twitter"

NEW_APP_HELP_TEMPLATE = """
You should create a new app from: https://apps.twitter.com/app/new

Next you have been configure it you should save consumer key and consumer
secret values to your config as the following keys:

    consumer key:    '{settings_ns}.consumer-key'
    consumer secret: '{settings_ns}.consumer-secret'

Once you have done this you must re-run this command to authorize the app
"""

AUTH_DONE_TEMPLATE = """
Authorization is done.

Save these values to your config:

    {settings_ns}.token = {token}
    {settings_ns}.token-secret = {token_secret}
"""


class TwitterNotifierCommand(pluginlib.Command):
    help = 'Authorize twitter notifier'

    arguments = (
        pluginlib.cliargument(
            '--test',
            dest='test',
            action='store_true',
            help='Say "hi!" on twitter'),

        pluginlib.cliargument(
            '--message',
            dest='message',
            default='Hi there!',
            help='Text to send to twitter'),

        pluginlib.cliargument(
            '--auth',
            dest='auth',
            action='store_true',
            help='Authorize app'),

        pluginlib.cliargument(
            '--consumer-key',
            dest='consumer_key',
            default=None,
            help='Application consumer key'),

        pluginlib.cliargument(
            '--consumer-secret',
            dest='consumer_secret',
            default=None,
            help='Application consumer secret'))

    def run(self, args):
        if args.auth:
            delattr(args, 'auth')
            return self._run_auth(args)

        elif args.test:
            delattr(args, 'test')
            return self._run_test(args)

    def _run_auth(self, args):
        consumer_key = args.consumer_key or self.app.settings.get(
            "{}.consumer-key".format(SETTINGS_NS),
            "")

        consumer_secret = args.consumer_secret or self.app.settings.get(
            "{}.consumer-secret".format(SETTINGS_NS),
            "")

        if not consumer_key or not consumer_secret:
            print(NEW_APP_HELP_TEMPLATE)
            return

        token, token_secret = twitter.oauth_dance(
            "", consumer_key, consumer_secret)

        print(AUTH_DONE_TEMPLATE.format(
            settings_ns=SETTINGS_NS,
            token=token,
            token_secret=token_secret))

    def _run_test(self, args):
        try:
            self.app._services['twitter-notifier']._api.send(args.message)
        except messaging.NotifierError as e:
            self.app.logger.warning(pprint.pformat(e.args))


class TwitterNotifierService(pluginlib.Service):
    def __init__(self, app):
        super().__init__(app)
        self._logger = self.app.logger.getChild('twitter-notifier')

        settings = self.app.settings.get_tree(SETTINGS_NS, {})

        keys = 'consumer-key consumer-secret token token-secret'.split()
        try:
            api_params = {k.replace('-', '_'): settings[k] for k in keys}
        except KeyError as e:
            msg = "Missing {ns}.{key} setting"
            msg = msg.format(ns=SETTINGS_NS, key=e.args[0])
            raise plugin.exc.PluginArgumentError(msg)

        notify_on = settings.get('notify-on', '')

        self.signals = {}
        for signal in [x.strip() for x in notify_on.split(',')]:
            if '=' in signal:
                k, v = signal.split('=', 1)
            else:
                k, v = signal, None

            if k not in self.signals:
                self.signals[k] = []
            self.signals[k].append(v)

        self.app.signals.connect('source-state-change', self.on_state_change)
        # app.signals.connect('origin-failed', self.on_origin_failed)

        self._api = ldottwitter.Twitter(**api_params)

    def on_state_change(self, sender, source):
        state = source.state_name

        # Check if this trigger is enabled
        if 'source-state-change' not in self.signals:
            return

        if self.signals['source-state-change'] is not None and \
           state not in self.signals['source-state-change']:
            return

        msg = r'[Arroyo] {source.name} is {source.state_name}'
        msg = msg.format(source=source)
        self._logger.info(msg)
        try:
            self._api.send(msg)
        except messaging.NotifierError as e:
            self.app.logger.warning(pprint.pformat(e.args))

    def on_origin_failed(self, sender, **kwargs):
        msg = r'[Arroyo] Origin failed: {}'
        msg = msg.format(repr(kwargs))

        self._logger.info(msg)
        try:
            self._api.send(msg)
        except messaging.NotifierError as e:
            self.app.logger.warning(pprint.pformat(e.args))


__arroyo_extensions__ = [
    TwitterNotifierService,
    TwitterNotifierComman
]
