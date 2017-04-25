# -*- coding: utf-8 -*-

# Copyright (C) 2015 Luis López <luis@cuarentaydos.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301,
# USA.


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
        'episode', 'episode-min', 'episode-max',
        'number', 'number-min', 'number-max'
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
            value = self.APPLIES_TO.normalize('series', value)

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
