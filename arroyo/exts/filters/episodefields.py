import functools


from arroyo import exts, models
from arroyo.exts.filters import common


class Filter(exts.Filter):
    _strs = ['series', 'series-glob']
    _nums = ('year', 'season', 'episode')
    _nums = [[x, x + '-min', x + '-max'] for x in _nums]
    _nums = functools.reduce(lambda x, y: x + y, _nums, [])

    APPLIES_TO = models.Episode
    HANDLES = _strs + _nums

    def alter_query(self, q):
        if self.key == 'series':
            self.key = 'series-glob'

        elif self.key == 'episode' or self.key.startswith('episode-'):
            self.key = self.key.replace('episode', 'number')

        elif self.key in self._nums:
            self.value = int(self.value)

        return common.alter_query_for_model_attr(
            q, models.Episode, self.key, self.value)


__arroyo_extensions__ = [
    ('filter', 'episode', Filter)
]
