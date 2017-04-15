# -*- coding: utf-8 -*-


from arroyo import pluginlib
from arroyo.pluginlib import filter


models = pluginlib.models


models = pluginlib.models


class Filter(pluginlib.QuerySetFilter):
    __extension_name__ = 'movie-fields'

    APPLIES_TO = models.Movie
    HANDLES = [
        'title', 'title-glob',
        'year', 'year-min', 'year-max',
    ]

    def alter(self, key, value, qs):
        # FIXME: Should we use normalization here?
        if key == 'title' or key.startswith('title-'):
            value = self.APPLIES_TO.normalize('title', value)

        # 'year' is integer
        if key == 'year' or key.startswith('year-'):
            value = int(value)

        return filter.alter_query_for_model_attr(
            qs, models.Movie, key, value)


__arroyo_extensions__ = [
    Filter
]
