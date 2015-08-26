from arroyo import plugin
from arroyo import models


class Query(plugin.Query):
    def matches(self, everything):
        qs = self.app.db.session.query(models.Source)

        if not everything:
            qs = qs.filter(models.Source.state == models.Source.State.NONE)

        items, params = self.app.selector.apply_filters(
            qs, [models.Source], dict(self.params))

        for k in params:
            msg = "Unknow filter {key}"
            msg = msg.format(key=k)
            self.app.logger.warning(msg)

        if params == self.params:
            return []

        return items


__arroyo_extensions__ = [
    ('source', Query)
]
