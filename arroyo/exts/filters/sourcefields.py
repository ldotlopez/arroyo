import functools


from ldotcommons import utils


from arroyo import exts, models
from arroyo.exts.filters import common


class Filter(exts.Filter):
    _strs = ('urn', 'uri', 'name', 'provider', 'language', 'type',
             'state-name')
    _strs = [[x, x + '-glob', x + '-regexp', x + '-in'] for x in _strs]
    _strs = functools.reduce(lambda x, y: x + y, _strs, [])

    _nums = ('id', 'size', 'seeds', 'leechers', 'share-ratio', 'state', 'age')
    _nums = [[x, x + '-min', x + '-max'] for x in _nums]
    _nums = functools.reduce(lambda x, y: x + y, _nums, [])

    APPLIES_TO = models.Source
    HANDLES = _strs + _nums + ['since']

    def alter_query(self, q):
        if self.key == 'size' or self.key.startswith('size-'):
            self.value = utils.parse_size(self.value)

        elif self.key == 'age' or self.key.startswith('age-'):
            self.value = utils.parse_interval(self.value)

        elif self.key == 'since':
            self.key = 'created-min'
            self.value = utils.parse_date(self.value)

        elif self.key in self._nums:
            self.value = int(self.value)

        return common.alter_query_for_model_attr(
            q, models.Source, self.key, self.value)


__arroyo_extensions__ = [
    ('filter', 'source', Filter)
]
