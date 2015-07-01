import functools
import re


import guessit
from ldotcommons import sqlalchemy as ldotsa, utils


from arroyo import exts, models


def alter_query_for_model_attr(q, model, key, value):
    # Get possible modifier from key
    m = re.search(
        r'(?P<key>(.+?))-(?P<mod>(glob|regexp|in|min|max))$', key)

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

    elif mod == 'glob':
        q = q.filter(attr.like(ldotsa.glob_to_like(value)))

    elif mod == 'like':
        q = q.filter(attr.like(value))

    elif mod == 'regexp':
        q = q.filter(attr.op('regexp')(value))

    elif mod == 'min':
        q = q.filter(attr >= value)

    elif mod == 'max':
        q = q.filter(attr <= value)

    else:
        raise TypeError(key)

    return q


class SourceFields(exts.Filter):
    _strs = ('urn', 'uri', 'name', 'provider', 'language', 'type',
             'state-name')
    _strs = [[x, x + '-glob', x + '-regexp', x + '-in'] for x in _strs]
    _strs = functools.reduce(lambda x, y: x + y, _strs, [])

    _nums = ('id', 'size', 'seeds', 'leechers', 'share-ratio', 'state', 'age')
    _nums = [[x, x + '-min', x + '-max'] for x in _nums]
    _nums = functools.reduce(lambda x, y: x + y, _nums, [])

    HANDLES = _strs + _nums
    SQL_AWARE = True

    def alter_query(self, q):

        if self.key == 'size' or self.key.startswith('size-'):
            self.value = utils.parse_size(self.value)

        elif self.key == 'age' or self.key.startswith('age-'):
            self.value = utils.parse_interval(self.value)

        elif self.key in self._nums:
            self.value = int(self.value)

        return alter_query_for_model_attr(
            q, models.Source, self.key, self.value)


class EpisodeFields(exts.Filter):
    _strs = ['series', 'series-glob']
    _nums = ('year', 'season', 'episode')
    _nums = [[x, x + '-min', x + '-max'] for x in _nums]
    _nums = functools.reduce(lambda x, y: x + y, _nums, [])

    HANDLES = _strs + _nums
    SQL_AWARE = True

    def alter_query(self, q):
        if self.key == 'series':
            self.key = 'series-glob'

        elif self.key == 'episode' or self.key.startswith('episode-'):
            self.key = self.key.replace('episode', 'number')

        elif self.key in self._nums:
            self.value = int(self.value)

        return alter_query_for_model_attr(
            q, models.Episode, self.key, self.value)


class MovieFields(exts.Filter):
    _strs = ['title', 'series-glob']
    _nums = ['year']
    _nums = [[x, x + '-min', x + '-max'] for x in _nums]
    _nums = functools.reduce(lambda x, y: x + y, _nums, [])

    HANDLES = _strs + _nums
    SQL_AWARE = True

    def alter_query(self, q):
        if self.key == 'title':
            self.key = 'title-glob'

        elif self.key == 'episode' or self.key.startswith('episode-'):
            self.key = self.key.replace('episode', 'number')

        elif self.key in self._nums:
            self.value = int(self.value)

        return alter_query_for_model_attr(
            q, models.Episode, self.key, self.value)


class QualityFilter(exts.Filter):
    APPLIES_TO = models.Source
    HANDLES = ('quality',)

    _SUPPORTED = ('1080p', '720p', '480p', 'hdtv')
    _SUPPORTED_STR = ", ".join("'{}'".format(x) for x in _SUPPORTED)

    def __init__(self, app, key, value):
        value = value.lower()

        if value not in self._SUPPORTED:
            msg = ("Quality '{quality}' not supported, "
                   "only {supported_qualities} are supported")

            msg = msg.format(
                quality=value,
                supported_qualities=self._SUPPORTED_STR)

            raise ValueError(msg)

        super().__init__(app, key, value)

    def filter(self, item):
        info = guessit.guess_episode_info(item.name)
        screen_size = info.get('screenSize', '').lower()
        fmt = info.get('format', '').lower()

        if self.value != 'hdtv':
            return self.value == screen_size
        else:
            return not screen_size and fmt == 'hdtv'

# class GenericFields:
#     def __init__(self, app, key, value):

#         # Get possible modifier from key
#         m = re.search(
#             r'(?P<key>(.+?))-(?P<mod>(glob|regexp|in|min|max))$', key)

#         if m:
#             key = m.group('key')
#             mod = m.group('mod')
#         else:
#             mod = None

#         # This filter access directly to source attributes.
#         # key must be normalize to model fields
#         key = key.replace('-', '_')

#         # Minor optimizations for glob modifier
#         if mod == 'glob':
#             value = value.lower()

#         super().__init__(app, key, value)
#         self.mod = mod
#         self._type_check = False

#     def filter(self, x):
#         f = getattr(self, 'check_' + (self.mod or 'raw'))
#         attr = getattr(x, self.key)

#         if attr is not None and not self._type_check:
#             if not isinstance(self.value, type(attr)):
#                 self.value = type(attr)(self.value)
#             self._type_check = True

#         return f(attr)

#     def check_raw(self, x):
#         return x == self.value

#     def check_glob(self, x):
#         return fnmatch.fnmatchcase(x.lower(), self.value)

#     def check_regexp(self, x):
#         return re.match(self.value, x, re.IGNORECASE)

#     def check_in(self, x):
#         raise NotImplementedError()

#     def check_min(self, x):
#         if x is None:
#             return False

#         return x >= self.value

#     def check_max(self, x):
#         if x is None:
#             return False

#         return x <= self.value


__arroyo_extensions__ = [
    ('filter', 'source', SourceFields),
    ('filter', 'episode', EpisodeFields),
    # ('filter', 'movie', MovieFields),
    ('filter', 'quality', QualityFilter),
]
