# -*- coding: utf-8 -*-


from arroyo import pluginlib
from arroyo.pluginlib import filter


models = pluginlib.models


class Filter(pluginlib.QuerySetFilter):
    __extension_name__ = 'movie-fields'

    APPLIES_TO = models.Movie
    HANDLES = [
        'title', 'title-glob',
        'year', 'year-min', 'year-max',
    ]

    def alter(self, key, value, qs):
        # For us, 'title' and 'title-glob' makes no difference
        if key == 'title':
            key = 'title-glob'

        # 'title' must be normalized
        # FIXME: Should this be there?
        if key == 'title' or key.startswith('title'):
            value = self.APPLIES_TO.normalize_title(value)

        # 'year' is integer
        if key == 'year' or key.startswith('year-'):
            value = int(value)

        return filter.alter_query_for_model_attr(
            qs, models.Movie, key, value)


__arroyo_extensions__ = [
    Filter
]
