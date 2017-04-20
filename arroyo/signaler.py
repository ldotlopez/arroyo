# -*- coding: utf-8 -*-

# Copyright (C) 2015 Luis López <luis@cuarentaydos.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301,
# USA.


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
