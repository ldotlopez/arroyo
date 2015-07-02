from arroyo import exts, models


class Query(exts.Query):
    def matches(self, everything):
        qs = self.app.db.session.query(models.Source).join(models.Movie)

        if not everything:
            qs = qs.filter(models.Movie.selection == None)  # nopep8

        items, params = self.apply_filters(
            qs, [models.Source, models.Movie], dict(self.params))

        for k in params:
            msg = "Unknow filter {key}"
            msg = msg.format(key=k)
            self.app.logger.warning(msg)

        if params == self.params:
            return []

        return items


__arroyo_extensions__ = [
    ('query', 'movie', Query)
]
