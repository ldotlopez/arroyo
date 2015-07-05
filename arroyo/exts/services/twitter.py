from ldotcommons.messaging import twitter as ldottwitter

from arroyo import (exc, exts)


class TwitterNotifier(exts.Service):
    SETTINGS_NS = 'extensions.services.twitter'

    def __init__(self, app):
        super().__init__(app)
        self._logger = self.app.logger.getChild('twitter-notifier')

        settings = self.app.settings.get_tree(self.SETTINGS_NS)

        keys = 'consumer-key consumer-secret token token-secret'.split()
        try:
            api_params = {k.replace('-', '_'): settings[k] for k in keys}
        except KeyError as e:
            msg = "Missing {ns}.{key} setting"
            msg = msg.format(ns=self.SETTINGS_NS, key=e.args[0])
            raise exc.ArgumentError(msg)

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
        self._api.send(msg)

    def on_origin_failed(self, sender, **kwargs):
        msg = r'[Arroyo] Origin failed: {}'
        msg = msg.format(repr(kwargs))

        self._logger.info(msg)
        self._api.send(msg)


__arroyo_extensions__ = [
    ('generic', 'twitter-notifier', TwitterNotifier)
]
