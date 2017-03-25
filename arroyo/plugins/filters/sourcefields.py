# -*- coding: utf-8 -*-

from arroyo import pluginlib
from arroyo.pluginlib import filter


import datetime
import functools
import time


import humanfriendly
from appkit import utils


models = pluginlib.models


class Filter(pluginlib.QuerySetFilter):
    __extension_name__ = 'source-fields'

    _strs = ('urn', 'uri', 'name', 'provider', 'language', 'type',
             'state-name')
    _strs = [[x, x + '-glob', x + '-in'] for x in _strs]
    _strs = functools.reduce(lambda x, y: x + y, _strs, [])

    _nums = ('id', 'size', 'seeds', 'leechers', 'share-ratio', 'state', 'age')
    _nums = [[x, x + '-min', x + '-max'] for x in _nums]
    _nums = functools.reduce(lambda x, y: x + y, _nums, [])

    APPLIES_TO = models.Source
    HANDLES = _strs + _nums + ['since']

    def alter(self, key, value, qs):
        def _convert_value(func):
            nonlocal value
            try:
                value = func(value)
            except ValueError as e:
                raise pluginlib.exc.SettingError(key, value, e)

        def _warn():
            msg = "Ignoring invalid setting '{key}': '{value}'"
            msg = msg.format(key=key, value=value)
            self.app.logger.warning(msg)

        if key == 'size' or key.startswith('size-'):
            _convert_value(utils.parse_size)

        elif key == 'age' or key.startswith('age-'):
            _convert_value(utils.parse_interval)

        elif key == 'since':
            x = humanfriendly.parse_date(value)
            x = datetime.datetime(*x).timetuple()
            x = time.mktime(x)
            x = int(x)

            key = 'created-min'
            value = x

        elif key in self._nums:
            _convert_value(float)

        return filter.alter_query_for_model_attr(
            qs, models.Source, key, value)


__arroyo_extensions__ = [
    Filter
]
