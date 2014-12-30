import blinker


class Signaler:
    def __init__(self):
        self._signals = {}

    @property
    def signals(self):
        return self._signals.keys()

    def register(self, name):
        if name in self._signals:
            msg = "Signal '{name}' was already registered"
            raise ValueError(msg.format(name=name))

        ret = blinker.signal(name)
        self._signals[name] = ret

        return ret

    def connect(self, name, call, **kwargs):
        self._signals[name].connect(call, **kwargs)

    def disconnect(self, name, call, **kwargs):
        self._signals[name].disconnect(call, **kwargs)

    def send(self, name, *args, **kwargs):
        self._signals[name].send(*args, **kwargs)
