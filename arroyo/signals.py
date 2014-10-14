# -*- coding: utf-8 -*-
# [SublimeLinter pep8-max-line-length:119]
# vim: set fileencoding=utf-8 :

import sys
import warnings

from ldotcommons import logging

import arroyo
from arroyo import models

warnings.warn('Use of arroyo.signals is disabled')
sys.exit(255)

ALL = object()


def connect(signal_name=ALL):
    signals = (signal_name,) if signal_name != ALL else _maps.keys()

    for signal in signals:
        if not signal in _maps:
            _logger.error("Unknow signal '{signal_name}'".format(signal_name=signal))
            continue

        _stores[signal] = []
        arroyo.SIGNALS[signal].connect(_maps[signal])


def disconnect(signal_name=ALL):
    signals = (signal_name,) if signal_name != ALL else _maps.keys()

    for signal in signals:
        if not signal in _maps:
            _logger.error("Unknow signal '{signal_name}'".format(signal_name=signal))
            continue

        arroyo.SIGNALS[signal].disconnect(_maps[signal])
        _stores[signal] = []


def get_store(name):
    return _stores[name]


def _on_source_add(sender, source, **kwargs):
    _stores['source-add'].append(source)


def _on_source_state_change(sender, source, **kwargs):
    if source.state == models.Source.State.NONE:
        return

    print("Source {}: {}".format(source.state_name, source.name))


_maps = {
    'source-add': _on_source_add,
    'source-state-change': _on_source_state_change
}

_stores = {k: [] for k in _maps}
_logger = logging.get_logger('arroyo.signals')
