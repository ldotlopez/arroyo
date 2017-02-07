# -*- coding: utf-8 -*-

from arroyo import pluginlib
from arroyo.pluginlib import query
models = pluginlib.models


class MovieQuery(query.HighLevelQuery):
    __extension_name__ = 'movie'

    KIND = 'movie'
    ENTITY_MODEL = models.Movie
    ENTITY_ATTR = 'movie'
    SELECTION_MODEL = models.MovieSelection

    @property
    def base_string(self):
        ret = self._get_base_string('title')
        if not ret:
            return super().base_string

        if 'year' in self.params:
            try:
                ret += ' {}'.format(int(self.params['year']))
            except ValueError:
                pass

        return ret

__arroyo_extensions__ = [
    MovieQuery
]
