from ldotcommons.messaging import twitter

from arroyo import plugins
from arroyo.app import app


@app.register('generic')
class TwitterNotifier:
    name = 'notifier.twitter'

    def __init__(self):
        if not app.config.has_section('plugin.twitter'):
            raise plugins.ArgumentError("Section [plugin.twitter] not found")

        keys = 'consumer_key consumer_secret token token_secret'.split()
        try:
            api_params = {k: app.config['plugin.twitter'][k] for k in keys}
        except KeyError as e:
            msg = "Section [plugin.twitter] doesn't have {key} key"
            raise plugins.ArgumentError(msg.format(key=e.args[0]))

        self._api = twitter.Twitter(**api_params)

        notify_on = app.config.get('plugin.twitter', 'notify_on', fallback='')

        self.signals = {}
        for signal in [x.strip() for x in notify_on.split(',')]:
            if '=' in signal:
                k, v = signal.split('=', 1)
            else:
                k, v = signal, None

            if k not in self.signals:
                self.signals[k] = []
            self.signals[k].append(v)

        app.signals.connect('source-state-change', self.on_state_change)
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
        self._api.send(msg.format(source=source))

    def on_origin_failed(self, sender, **kwargs):
        self._api.send(r'[Arroyo] Origin failed: {}'.format(repr(kwargs)))
