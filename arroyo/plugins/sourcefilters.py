# -*- coding: utf-8 -*-

from arroyo import plugin
from arroyo.plugin.tools import filter


import datetime
import functools
import time

import humanfriendly
from ldotcommons import utils


class Filter(plugin.Filter):
    _strs = ('urn', 'uri', 'name', 'provider', 'language', 'type',
             'state-name')
    _strs = [[x, x + '-glob', x + '-regexp', x + '-in'] for x in _strs]
    _strs = functools.reduce(lambda x, y: x + y, _strs, [])

    _nums = ('id', 'size', 'seeds', 'leechers', 'share-ratio', 'state', 'age')
    _nums = [[x, x + '-min', x + '-max'] for x in _nums]
    _nums = functools.reduce(lambda x, y: x + y, _nums, [])

    APPLIES_TO = plugin.models.Source
    HANDLES = _strs + _nums + ['since']

    def alter_query(self, q):
        def _convert_value(func):
            try:
                self.value = func(self.value)
            except ValueError as e:
                raise plugin.exc.SettingError(self.key, self.value, e)

        def _warn():
            msg = "Ignoring invalid setting '{key}': '{value}'"
            msg = msg.format(key=self.key, value=self.value)
            self.app.logger.warning(msg)

        if self.key == 'size' or self.key.startswith('size-'):
            _convert_value(utils.parse_size)

        elif self.key == 'age' or self.key.startswith('age-'):
            _convert_value(utils.parse_interval)

        elif self.key == 'since':
            x = humanfriendly.parse_date(self.value)
            x = datetime.datetime(*x).timetuple()
            x = time.mktime(x)
            x = int(x)

            self.key = 'created-min'
            self.value = x

        elif self.key in self._nums:
            _convert_value(float)

        return filter.alter_query_for_model_attr(
            q, plugin.models.Source, self.key, self.value)


__arroyo_extensions__ = [
    ('source', Filter)
]
