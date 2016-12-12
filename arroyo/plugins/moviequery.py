# -*- coding: utf-8 -*-

from arroyo import plugin
from arroyo.plugin.tools import query


class MovieQuery(query.HighLevelQuery):
    KIND = 'movie'
    ENTITY_MODEL = plugin.models.Movie
    ENTITY_ATTR = 'movie'
    SELECTION_MODEL = plugin.models.MovieSelection

    @property
    def base_string(self):
        ret = self._get_base_string('title')

        if 'year' in self.params:
            ret += ' {}'.format(self.params['year'])

        return ret

__arroyo_extensions__ = [
    ('movie', MovieQuery)
]
