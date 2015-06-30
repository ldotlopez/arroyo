import functools
from glob import fnmatch
import re

from arroyo import exts, models


_strs = ('urn', 'uri', 'name', 'provider', 'language', 'type', 'state-name')
_nums = ('id', 'size', 'seeds', 'leechers', 'share-ratio', 'state', 'age')

_strs = [[x, x + '-glob', x + '-regexp', x + '-in'] for x in _strs]
_nums = [[x, x + '-min', x + '-max'] for x in _nums]

_handles = (
    functools.reduce(lambda x, y: x + y, _strs, []) +
    functools.reduce(lambda x, y: x + y, _nums, []))


# class SimpleFilter(exts.Filter):
#     APPLIES_TO = models.Source
#     HANDLES = 'name-glob', 'name'
#
#     def __init___(self, app, key, value):
#         if key == 'name-glob':
#             value = value.lower()
#
#         super().__init__(app, key, value)
#
#     def filter(self, x):
#         return getattr(self, 'filter_' + self.key.replace('-', '_'))(x)
#
#     def filter_name(self, x):
#         return x.name == self.value
#
#     def filter_name_glob(self, x):
#         return fnmatch.fnmatchcase(x.name.lower(), self.value)


class GenericFields:
    def __init__(self, app, key, value):

        # Get possible modifier from key
        m = re.search(r'(?P<key>(.+?))-(?P<mod>(glob|regexp|in|min|max))$', key)
        if m:
            key = m.group('key')
            mod = m.group('mod')
        else:
            mod = None

        # This filter access directly to source attributes.
        # key must be normalize to model fields
        key = key.replace('-', '_')

        # Minor optimizations for glob modifier
        if mod == 'glob':
            value = value.lower()

        super().__init__(app, key, value)
        self.mod = mod

    def filter(self, x):
        return getattr(self, 'check_' + (self.mod or 'raw'))(getattr(x, self.key))

    def check_raw(self, x):
        return x == self.value

    def check_glob(self, x):
        return fnmatch.fnmatchcase(x.lower(), self.value)

    def check_regexp(self, x):
        return re.match(self.value, x, re.IGNORECASE)

    def check_in(self, x):
        raise NotImplementedError()

    def check_min(self, x):
        return x >= self.value

    def check_max(self, x):
        return x <= self.value


class SourceFields(GenericFields, exts.Filter):
    APPLIES_TO = models.Source
    HANDLES = _handles


class EpisodeFields(GenericFields, exts.Filter):
    APPLIES_TO = models.Episode
    HANDLES = ('series', 'series-glob')

    def __init__(self, app, key, value):
        if key == 'series':
            key = 'series-glob'

        super().__init__(app, key, value)


__arroyo_extensions__ = [
    ('filter', 'simple', SourceFields),
    ('filter', 'episodefields', EpisodeFields)
]
