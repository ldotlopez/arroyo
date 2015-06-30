from arroyo import (
    exts,
    models
)


class Query(exts.Query):
    def matches(self, everything):
        qs = self.app.db.session.query(models.Source)
        if not everything:
            qs = qs.filter(models.Source.state == models.Source.State.NONE)

        return self.apply_filters(models.Source, qs.all())


__arroyo_extensions__ = [
    ('query', 'source', Query)
]
