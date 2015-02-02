from ldotcommons import utils


from arroyo import (
    exts,
    models
)


class Selector(exts.Selector):
    def __init__(self, app, **filters):
        super(Selector, self).__init__(app)
        self._filters = filters.copy()

    def _filter(self, query, key, value):
        if '_' in key:
            mod = key.split('_')[-1]
            key = '_'.join(key.split('_')[:-1])
        else:
            key = key
            mod = None

        attr = getattr(models.Source, key, None)

        if mod == 'like':
            query = query.filter(attr.like(value))

        elif mod == 'regexp':
            query = query.filter(attr.op('regexp')(value))

        elif mod == 'min':
            value = utils.parse_size(value)
            query = query.filter(attr >= value)

        elif mod == 'max':
            value = utils.parse_size(value)
            query = query.filter(attr <= value)

        else:
            query = query.filter(attr == value)

        return query

    def list(self):
        qs = self.app.db.session.query(models.Source)

        for (k, v) in self._filters.items():
            qs = self._filter(qs, k, v)

        for src in qs:
            yield src

    def select(self):
        return self.list()


__arroyo_extensions__ = [
    ('selector', 'source', Selector)
]
