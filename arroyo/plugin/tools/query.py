from arroyo import plugin


class HighLevelQuery(plugin.Query):
    def matches(self, everything):
        qs = self.app.db.session.query(plugin.models.Source)
        qs = qs.join(self.ENTITY_MODEL)
        if not everything:
            qs = qs.filter(
                plugin.models.Source.state == plugin.models.Source.State.NONE)
            qs = qs.filter(
                self.ENTITY_MODEL.selection == None)  # nopep8

        items, params = self.app.selector.apply_filters(
            qs, [plugin.models.Source, self.ENTITY_MODEL], dict(self.params))

        for k in params:
            msg = "Unknow filter {key}"
            msg = msg.format(key=k)
            self.app.logger.warning(msg)

        if params == self.params:
            return []

        return items
