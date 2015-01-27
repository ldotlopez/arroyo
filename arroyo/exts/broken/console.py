from arroyo.app import app


@app.register('generic')
class ConsoleNotifier:
    name = 'notifier.console'

    def __init__(self):
        app.signals.connect('source-added', self.on_source)
        app.signals.connect('source-updated', self.on_source)

    def on_source(self, *args, **kwargs):
        print(repr(args), repr(kwargs))
