from arroyo import plugin


class HighLevelQuery(plugin.Query):
    def get_query_set(self, session, everything=False):
        qs = session.query(plugin.models.Source)
        qs = qs.join(self.ENTITY_MODEL)
        if not everything:
            qs = qs.filter(
                plugin.models.Source.state == plugin.models.Source.State.NONE)
            qs = qs.filter(
                self.ENTITY_MODEL.selection == None)  # nopep8

        return qs
