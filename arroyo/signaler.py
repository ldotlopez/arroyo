# -*- coding: utf-8 -*-

# IMPORTANT NOTE:
# Previous implementation uses blinker packager.
# Blinker uses global state for keeping references to signals and callbacks.
# This causes some bugs in tests (and potentially in real world) because
# Arroyo instances and sqlalchemy sessions are hold.
# This implementation tries to mimic blinked as much as possible

import warnings


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

        self._signals[name] = []

    def connect(self, name, callback, *args, **kwargs):
        if args or kwargs:
            msg = "Code is using deprecated blinker.connect API"
            warnings.warn(msg)

        self.get_signal(name).append(callback)

    def disconnect(self, name, callback, *args, **kwargs):
        if args or kwargs:
            msg = "Code is using deprecated blinker.connect API"
            warnings.warn(msg)

        self.get_signal(name).remove(callback)

    def send(self, name, *args, **kwargs):
        ret = []
        for callback in self.get_signal(name):
            callback_ret = callback(*args, sender=None, **kwargs)
            ret.append((callback, callback_ret))

        return ret

# import blinker
#
#
# class Signaler:
#     def __init__(self):
#         self._signals = {}
#
#     @property
#     def signals(self):
#         return self._signals.keys()
#
#     def get_signal(self, name):
#         return self._signals[name]
#
#     def register(self, name):
#         if name in self._signals:
#             msg = "Signal '{name}' was already registered"
#             raise ValueError(msg.format(name=name))
#
#         ret = blinker.signal(name)
#         self._signals[name] = ret
#
#         return ret
#
#     def connect(self, name, call, **kwargs):
#         self.get_signal(name).connect(call, **kwargs)
#
#     def disconnect(self, name, call, **kwargs):
#         self.get_signal(name).disconnect(call, **kwargs)
#
#     def send(self, name, **kwargs):
#         self.get_signal(name).send(**kwargs)
