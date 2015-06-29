from ldotcommons import utils
import functools
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


class Query(exts.Query):
    HANDLES = _handles

    def __init__(self, app, spec):
        super().__init__(app, spec)
        self._logger = app.logger.getChild('source-selector')

    def _filter(self, qs, key, value):
        def _split_key(key):
            if '-' in key:
                mod = key.split('-')[-1]
                key = '-'.join(key.split('-')[:-1])
            else:
                mod = None

            return (key, mod)

        key, mod = _split_key(key)

        if key not in self.HANDLES:
            msg = ("Unknow attribute parameter '{parameter}'. "
                   "Are you using the right selector?")
            msg = msg.format(parameter=key)
            self._logger.warning(msg)
            return qs

        attr = getattr(models.Source, key)

        if mod is None:
            qs = qs.filter(attr == value)

        elif mod == 'like':
            qs = qs.filter(attr.like(value))

        elif mod == 'regexp':
            qs = qs.filter(attr.op('regexp')(value))

        elif mod == 'in':
            raise NotImplementedError()

        elif mod == 'min':
            value = utils.parse_size(value)
            qs = qs.filter(attr >= value)

        elif mod == 'max':
            value = utils.parse_size(value)
            qs = qs.filter(attr <= value)

        else:
            msg = "Unknow modifier '{mod}' for '{key}'."
            msg = msg.format(mod=mod, key=key)
            self._logger.warning(msg)

        return qs

    def matches(self, everything):
        qs = self.app.db.session.query(models.Source)
        if not everything:
            qs = qs.filter(models.Source.state == models.Source.State.NONE)

        qs = functools.reduce(
            lambda qs, pair: self._filter(qs, *pair),
            self.spec.items(),
            qs)

        return qs.all()

__arroyo_extensions__ = [
    ('query', 'source', Query)
]
