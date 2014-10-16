from arroyo.app import app
from arroyo.signals import SIGNALS

class ConsoleNotifier:
	name = 'notifier.console'

	def __init__(self):
		SIGNALS['source-added'].connect(self.on_source)
		SIGNALS['source-updated'].connect(self.on_source)

	def on_source(self, *args, **kwargs):
		print(repr(args), repr(kwargs))

app.register_plugin(ConsoleNotifier)