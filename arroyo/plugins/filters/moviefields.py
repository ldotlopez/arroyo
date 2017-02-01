# -*- coding: utf-8 -*-

from arroyo import pluginlib
from arroyo.pluginlib import filter
models = pluginlib.models


import functools


class Filter(pluginlib.QuerySetFilter):
    __extension_name__ = 'movie-fields'

    _strs = ['title', 'title-glob']
    _nums = ['year']
    _nums = [[x, x + '-min', x + '-max'] for x in _nums]
    _nums = functools.reduce(lambda x, y: x + y, _nums, [])

    APPLIES_TO = models.Movie
    HANDLES = _strs + _nums

    def alter(self, key, value, qs):
        if key == 'title':
            key = 'title-glob'

        elif key == 'episode' or key.startswith('episode-'):
            key = key.replace('episode', 'number')

        elif key in self._nums:
            value = int(value)

        return filter.alter_query_for_model_attr(
            qs, models.Movie, key, value)


__arroyo_extensions__ = [
    Filter
]
