# -*- coding: utf-8 -*-

from arroyo import pluginlib
from arroyo.pluginlib import filter


import functools


models = pluginlib.models


class Filter(pluginlib.QuerySetFilter):
    __extension_name__ = 'episode-fields'

    _strs = ['series', 'series-glob']
    _nums = ('year', 'season', 'episode')
    _nums = [[x, x + '-min', x + '-max'] for x in _nums]
    _nums = functools.reduce(lambda x, y: x + y, _nums, [])

    APPLIES_TO = models.Episode
    HANDLES = _strs + _nums

    def alter(self, key, value, qs):
        if key == 'series':
            key = 'series-glob'

        elif key == 'episode' or key.startswith('episode-'):
            key = key.replace('episode', 'number')

        elif key in self._nums:
            value = int(value)

        return filter.alter_query_for_model_attr(
            qs, models.Episode, key, value)


__arroyo_extensions__ = [
    Filter
]
