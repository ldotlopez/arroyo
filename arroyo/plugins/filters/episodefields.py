# -*- coding: utf-8 -*-


from arroyo import pluginlib
from arroyo.pluginlib import filter


models = pluginlib.models


class Filter(pluginlib.QuerySetFilter):
    __extension_name__ = 'episode-fields'

    APPLIES_TO = models.Episode
    HANDLES = [
        'series', 'series-glob',
        'year', 'year-min', 'year-max',
        'season', 'season-min', 'season-max',
        'episode', 'episode-min', 'episode-max'
    ]

    def alter(self, key, value, qs):
        # For us, 'series' and 'series-glob' makes no difference
        if key == 'series':
            key = 'series-glob'

        # Rename 'episode' to 'number'
        # FIXME: this shouldn't be here
        elif key == 'episode' or key.startswith('episode-'):
            key = key.replace('episode', 'number')

        # 'series' must be normalized
        # FIXME: Should this be there?
        if key == 'series' or key.startswith('series'):
            value = self.APPLIES_TO.normalize_series(value)

        # 'year', 'season' and 'episode' are integers
        if (key == 'year' or key.startswith('year-') or
                key == 'season' or key.startswith('season-') or
                key == 'number' or key.startswith('number-')):
            value = int(value)

        return filter.alter_query_for_model_attr(
            qs, models.Episode, key, value)


__arroyo_extensions__ = [
    Filter
]
