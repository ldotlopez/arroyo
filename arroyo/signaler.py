# -*- coding: utf-8 -*-

import blinker


class Signaler:
    def __init__(self):
        self._signals = {}

    @property
    def signals(self):
        return self._signals.keys()

    def get_signal(self, name):
        return self._signals[name]

    def register(self, name):
        if name in self._signals:
            msg = "Signal '{name}' was already registered"
            raise ValueError(msg.format(name=name))

        ret = blinker.Signal()
        self._signals[name] = ret

        return ret

    def connect(self, name, call, **kwargs):
        self.get_signal(name).connect(call, **kwargs)

    def disconnect(self, name, call, **kwargs):
        self.get_signal(name).disconnect(call, **kwargs)

    def send(self, name, **kwargs):
        self.get_signal(name).send(**kwargs)
