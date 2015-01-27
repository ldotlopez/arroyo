import blinker


from arroyo import exc


class Signaler:
    def __init__(self):
        self._signals = {}

    @property
    def signals(self):
        return self._signals.keys()

    def get_signal(self, name):
        try:
            return self._signals[name]
        except KeyError as e:
            raise exc.UnknowSignal(e.args[0])

    def register(self, name):
        if name in self._signals:
            msg = "Signal '{name}' was already registered"
            raise ValueError(msg.format(name=name))

        ret = blinker.signal(name)
        self._signals[name] = ret

        return ret

    def connect(self, name, call, **kwargs):
        self.get_signal(name).connect(call, **kwargs)

    def disconnect(self, name, call, **kwargs):
        self.get_signal(name).disconnect(call, **kwargs)

    def send(self, name, *args, **kwargs):
        self.get_signal(name).send(*args, **kwargs)
