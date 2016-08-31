# -*- coding: utf-8 -*-

from arroyo import plugin
from arroyo.plugin.tools import filter


import functools


class MovieFilters(plugin.Filter):
    __extension_name__ = 'movie-filters'

    _strs = ['title', 'title-glob']
    _nums = ['year']
    _nums = [[x, x + '-min', x + '-max'] for x in _nums]
    _nums = functools.reduce(lambda x, y: x + y, _nums, [])

    APPLIES_TO = plugin.models.Movie
    HANDLES = _strs + _nums

    def alter_query(self, q):
        if self.key == 'title':
            self.key = 'title-glob'

        elif self.key == 'episode' or self.key.startswith('episode-'):
            self.key = self.key.replace('episode', 'number')

        elif self.key in self._nums:
            self.value = int(self.value)

        return filter.alter_query_for_model_attr(
            q, plugin.models.Movie, self.key, self.value)


__arroyo_extensions__ = [
    MovieFilters
]
