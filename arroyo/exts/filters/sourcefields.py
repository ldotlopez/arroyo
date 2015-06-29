import functools
from ldotcommons import utils
from arroyo import (
    exts,
    models
)


_strs = ('urn', 'uri', 'name', 'provider', 'language', 'type', 'state-name')
_nums = ('id', 'size', 'seeds', 'leechers', 'share-ratio', 'state', 'age')

_strs = [[x, x + '-like', x + '-regexp', x + '-in'] for x in _strs]
_nums = [[x, x + '-min', x + '-max'] for x in _nums]

_handles = (
    functools.reduce(lambda x, y: x + y, _strs, []) +
    functools.reduce(lambda x, y: x + y, _nums, []))


class SourceFields(exts.Filter):
    APPLIES_ON = models.Source
    HANDLES = _handles

    def filter(self, item):
        def _split_key(key):
            if '-' in key:
                mod = key.split('-')[-1]
                key = '-'.join(key.split('-')[:-1])
            else:
                mod = None

            return (key, mod)

        key, mod = _split_key(self.key)
        value = self.value

        if mod is None:
            return getattr(item, key) == value

        # attr = getattr(models.Source, key)

        # if mod is None:
        #     qs = qs.filter(attr == value)

        # elif mod == 'like':
        #     qs = qs.filter(attr.like(value))

        # elif mod == 'regexp':
        #     qs = qs.filter(attr.op('regexp')(value))

        # elif mod == 'in':
        #     raise NotImplementedError()

        # elif mod == 'min':
        #     value = utils.parse_size(value)
        #     qs = qs.filter(attr >= value)

        # elif mod == 'max':
        #     value = utils.parse_size(value)
        #     qs = qs.filter(attr <= value)

        return False

    def apply(self, items):
        return list(filter(self.filter, items))

__arroyo_extensions__ = [
    ('filter', 'sourcefields', SourceFields)
]
