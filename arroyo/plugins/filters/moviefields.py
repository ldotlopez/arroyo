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
