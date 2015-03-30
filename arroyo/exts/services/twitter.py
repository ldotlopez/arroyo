from ldotcommons.messaging import twitter as ldottwitter

from arroyo import (exc, exts)


class TwitterNotifier(exts.Service):
    _SECTION_NAME = 'extension.services.twitter'

    def __init__(self, app):
        super(TwitterNotifier, self).__init__(app)
        self._logger = self.app.logger.getChild('twitter-notifier')

        if not self.app.config.has_section(self._SECTION_NAME):
            msg = "Section [{section_name}] not found"
            msg = msg.format(section_name=self._SECTION_NAME)
            raise exc.ArgumentError(msg)

        keys = 'consumer_key consumer_secret token token_secret'.split()
        try:
            api_params = {k: self.app.config[self._SECTION_NAME][k]
                          for k in keys}
        except KeyError as e:
            msg = "Section [{section_name}] doesn't have {key} key"
            msg = msg.format(section_name=self._SECTION_NAME, key=e.args[0])
            raise exc.ArgumentError(msg)

        self._api = ldottwitter.Twitter(**api_params)

        notify_on = self.app.config.get(self._SECTION_NAME,
                                        'notify_on',
                                        fallback='')

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
