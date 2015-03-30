from ldotcommons import utils


from arroyo import (
    exts,
    models
)


class Selector(exts.Selector):
    def __init__(self, app, query):
        super(Selector, self).__init__(app)
        self._query = query

    def _filter(self, qs, key, value):
        if '_' in key:
            mod = key.split('_')[-1]
            key = '_'.join(key.split('_')[:-1])
        else:
            key = key
            mod = None

        attr = getattr(models.Source, key, None)

        if mod == 'like':
            qs = qs.filter(attr.like(value))

        elif mod == 'regexp':
            qs = qs.filter(attr.op('regexp')(value))

        elif mod == 'min':
            value = utils.parse_size(value)
            qs = qs.filter(attr >= value)

        elif mod == 'max':
            value = utils.parse_size(value)
            qs = qs.filter(attr <= value)

        else:
            qs = qs.filter(attr == value)

        return qs

    def select(self, everything):
        qs = self.app.db.session.query(models.Source)

        for (k, v) in self._query.items():
            qs = self._filter(qs, k, v)

        if not everything:
            qs = qs.filter(models.Source.state == models.Source.State.NONE)

        for src in qs:
            yield src


__arroyo_extensions__ = [
    ('selector', 'source', Selector)
]
