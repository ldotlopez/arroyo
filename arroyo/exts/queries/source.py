from arroyo import (
    exts,
    models
)


class Query(exts.Query):
    def matches(self, everything):
        qs = self.app.db.session.query(models.Source)

        if not everything:
            qs = qs.filter(models.Source.state == models.Source.State.NONE)

        items, params = self.apply_filters(qs, dict(self.params))

        for k in params:
            msg = "Unknow filter {key}"
            msg = msg.format(key=k)
            self.app.logger.warning(msg)

        if params == self.params:
            return []

        return items

__arroyo_extensions__ = [
    ('query', 'source', Query)
]
