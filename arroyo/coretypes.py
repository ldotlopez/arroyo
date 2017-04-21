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


from collections import abc


class BaseQuery(abc.Mapping):
    def __init__(self, **params):
        def _normalize_key(key):
            for x in [' ', '_']:
                key = key.replace(x, '-')
            return key

        super().__init__()
        self._items = {}

        for (param, value) in params.items():
            try:
                param = str(param)
            except ValueError as e:
                msg = ("Invalid param '{param}'. "
                       "All params must be non empty strings")
                msg = msg.format(param=param)
                raise ValueError(msg) from e
            param = param.replace('_', '-')

            if param.endswith('-in'):
                if not isinstance(value, list):
                    msg = ("Invalid value '{value}' for param '{param}'. "
                           "Expected list value for '-in' parameter")
                    msg = msg.format(param=param, value=value)
                    raise ValueError(msg)

                try:
                    value = [str(x) for x in value]

                except ValueError as e:
                    msg = ("Invalid value '{value}' for param '{param}'. "
                           "Expected list of strings value for parameter")
                    msg = msg.format(param=param, value=value)
                    raise ValueError(msg) from e

            else:
                try:
                    value = str(value)
                except ValueError as e:
                    msg = ("Invalid value '{value}' for param '{param}'. "
                           "All values must be non empty strings")
                    msg = msg.format(param=param, value=value)
                    raise ValueError(msg) from e

            # FIXME: Deprecation code
            if param == 'kind':
                msg = "kind paramater for queries is deprecated. Use 'type'"
                raise ValueError(msg)

            self._items[param] = value

    def __iter__(self):
        yield from self._items.__iter__()

    def __getitem__(self, item):
        return self._items[item]

    def __len__(self):
        return len(self._items)

    def asdict(self):
        return self._items.copy()

    @property
    def base_string(self):
        raise NotImplementedError()

    def _get_base_string(self, base_key='name'):
        ret = None

        if base_key in self:
            ret = self[base_key]

        elif base_key+'-glob' in self:
            ret = self[base_key+'-glob'].replace('*', ' ')
            ret = ret.replace('.', ' ')

        return ret.strip() if ret else None

    def __eq__(self, other):
        return isinstance(other, BaseQuery) and self.asdict() == other.asdict()

    def __repr__(self):
        params = ['{param}={value}'.format(param=p, value=v)
                  for (p, v) in self._items.items()]
        params = ', '.join(params)

        return '<{cls} 0x{id:x} {params}>'.format(
            cls=self.__class__.__name__,
            id=id(self),
            params=params)


class SourceQuery(BaseQuery):
    def __init__(self, **params):
        if 'language' in params:
            params['language'] = params['language'].lower()

        if 'type' in params:
            params['type'] = params['type'].lower()

        super().__init__(**params)

    @property
    def base_string(self):
        return self._get_base_string('name')


class EpisodeQuery(BaseQuery):
    def __init__(self, *args, **kwargs):
        kwargs_ = {'year': None}
        kwargs_.update(kwargs)
        super().__init__(*args, **kwargs_)

    @property
    def base_string(self):
        ret = self._get_base_string('series')
        if not ret:
            return super().base_string

        params = {}
        for key in ['year', 'season', 'episode']:
            try:
                params[key] = int(self[key])
            except (KeyError, ValueError):
                pass

        if 'year' in params:
            ret += ' {}'.format(params['year'])

        if 'season' in params:
            ret += ' S{:02d}'.format(params['season'])

            if 'episode' in params:
                ret += 'E{:02d}'.format(params['episode'])

        return ret


class MovieQuery(BaseQuery):
    def __init__(self, *args, **kwargs):
        kwargs_ = {'year': None}
        kwargs_.update(kwargs)
        super().__init__(*args, **kwargs_)

    @property
    def base_string(self):
        ret = self._get_base_string('title')
        if not ret:
            return super().base_string

        if 'year' in self:
            try:
                ret += ' {}'.format(int(self['year']))
            except ValueError:
                pass

        return ret


def Query(**params):
    params = params.copy()
    params['type'] = params.get('type', 'source')
    params['state'] = params.get('state', 'none')

    if params['type'] == 'source':
        return SourceQuery(**params)

    elif params['type'] == 'episode':
        return EpisodeQuery(**params)

    elif params['type'] == 'movie':
        return MovieQuery(**params)

    else:
        raise ValueError('type='+params['type'])
