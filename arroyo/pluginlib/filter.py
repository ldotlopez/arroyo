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


import re


from appkit.db import sqlalchemyutils as sautils


def alter_query_for_model_attr(q, model, key, value):
    # Get possible modifier from key
    m = re.search(
        r'(?P<key>(.+?))-(?P<mod>(regexp|glob|in|min|max))$', key)

    if m:
        key = m.group('key')
        mod = m.group('mod')
    else:
        mod = None

    # To access directly to source attributes key must be normalize to model
    # fields standards
    key = key.replace('-', '_')

    # Minor optimizations for glob modifier
    if mod == 'glob':
        value = value.lower()

    # Extract attr
    attr = getattr(model, key)

    if mod is None:
        q = q.filter(attr == value)

    elif mod == 'regexp':
        q = q.filter(attr.op('regexp')(value))

    elif mod == 'glob':
        q = q.filter(attr.like(sautils.glob_to_like(value)))

    elif mod == 'min':
        q = q.filter(attr >= value)

    elif mod == 'max':
        q = q.filter(attr <= value)

    else:
        raise TypeError(key)

    return q
