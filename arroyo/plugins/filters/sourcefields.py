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


import datetime
import functools
import time


import humanfriendly
from appkit import utils

models = pluginlib.models


class SourceFieldsFilter(pluginlib.QuerySetFilter):
    __extension_name__ = 'source-fields'

    _strs = ('urn', 'uri', 'name', 'provider', 'language')
    _strs = [[x, x + '-regexp', x + '-glob', x + '-in'] for x in _strs]
    _strs = functools.reduce(lambda x, y: x + y, _strs, [])

    _nums = ('id', 'size', 'seeds', 'leechers', 'share-ratio', 'age')
    _nums = [[x, x + '-min', x + '-max'] for x in _nums]
    _nums = functools.reduce(lambda x, y: x + y, _nums, [])

    APPLIES_TO = pluginlib.models.Source
    HANDLES = _strs + _nums + ['since']

    def alter(self, key, value, qs):
        def _convert_value(func):
            nonlocal value
            try:
                value = func(value)
            except ValueError as e:
                raise

        if key == 'size' or key.startswith('size-'):
            _convert_value(utils.parse_size)

        elif key == 'age' or key.startswith('age-'):
            _convert_value(utils.parse_interval)

        elif key == 'since':
            x = humanfriendly.parse_date(value)
            x = datetime.datetime(*x).timetuple()
            x = time.mktime(x)
            x = int(x)

            key = 'created-min'
            value = x

        elif key in self._nums:
            _convert_value(float)

        return filter.alter_query_for_model_attr(
            qs, pluginlib.models.Source, key, value)


class CompatFilter(pluginlib.IterableFilter):
    __extension_name__ = 'compatibility-filter'

    APPLIES_TO = pluginlib.models.Source
    HANDLES = ['state', 'type', 'kind', 'entity']  # FIXME: Deprecation

    def filter(self, key, value, item):
        # FIXME: Deprecation
        if key in ['kind', 'entity']:
            key = 'type'

        if key == 'type':
            return self.filter_type(value, item)

        elif key == 'state':
            return self.filter_state(value, item)

    def filter_type(self, type, item):
        if type == 'source':
            return isinstance(item, models.Source)

        if item.entity is None:
            return item.type == type

        if type == 'episode':
            return isinstance(item.entity, models.Episode)

        elif type == 'movie':
            return isinstance(item.entity, models.Movie)

    def filter_state(self, state, item):
        # Don't exclude anything
        if state == 'all':
            return True

        # If state is not NONE drop it
        if item.state != models.State.NONE:
            return False

        # State can be None but we have to check if matching entity has no
        # selection
        if item.entity and item.entity.selection is not None:
            return False

        # Nothing to do
        return True


__arroyo_extensions__ = [
    SourceFieldsFilter,
    CompatFilter,
]
