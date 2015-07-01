import functools
from glob import fnmatch
import guessit
import re


from arroyo import exts, models


class GenericFields:
    def __init__(self, app, key, value):

        # Get possible modifier from key
        m = re.search(
            r'(?P<key>(.+?))-(?P<mod>(glob|regexp|in|min|max))$', key)

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
        self._type_check = False

    def filter(self, x):
        f = getattr(self, 'check_' + (self.mod or 'raw'))
        attr = getattr(x, self.key)

        if attr is not None and not self._type_check:
            if not isinstance(self.value, type(attr)):
                self.value = type(attr)(self.value)
            self._type_check = True

        return f(attr)

    def check_raw(self, x):
        return x == self.value

    def check_glob(self, x):
        return fnmatch.fnmatchcase(x.lower(), self.value)

    def check_regexp(self, x):
        return re.match(self.value, x, re.IGNORECASE)

    def check_in(self, x):
        raise NotImplementedError()

    def check_min(self, x):
        if x is None:
            return False

        return x >= self.value

    def check_max(self, x):
        if x is None:
            return False

        return x <= self.value


#
# SourceFields
#


class SourceFields(GenericFields, exts.Filter):
    _strs = ('urn', 'uri', 'name', 'provider', 'language', 'type',
             'state-name')
    _nums = ('id', 'size', 'seeds', 'leechers', 'share-ratio', 'state', 'age')

    _strs = [[x, x + '-glob', x + '-regexp', x + '-in'] for x in _strs]
    _nums = [[x, x + '-min', x + '-max'] for x in _nums]

    _handles = (
        functools.reduce(lambda x, y: x + y, _strs, []) +
        functools.reduce(lambda x, y: x + y, _nums, []))

    APPLIES_TO = models.Source
    HANDLES = _handles


#
# EpisodeFields
#


class EpisodeFields(GenericFields, exts.Filter):
    APPLIES_TO = models.Episode
    HANDLES = (
        'series', 'series-glob',
        'year', 'year-min', 'year-max',
        'season', 'season-min', 'season-max',
        'episode', 'episode-min', 'episode-max'
    )

    def __init__(self, app, key, value):
        if key == 'series':
            key = 'series-glob'

        if key == 'episode' or key.startswith('episode-'):
            key = key.replace('episode', 'number')

        super().__init__(app, key, value)
        print(self.key)

#
# Quality
#


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


__arroyo_extensions__ = [
    ('filter', 'simple', SourceFields),
    ('filter', 'episodefields', EpisodeFields),
    ('filter', 'quality', QualityFilter),
]
