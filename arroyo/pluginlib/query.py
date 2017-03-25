from arroyo import pluginlib
models = pluginlib.models


class HighLevelQuery(pluginlib.Query):
    def get_query_set(self, session, everything=False):
        qs = session.query(models.Source)
        qs = qs.join(self.ENTITY_MODEL)
        if not everything:
            qs = qs.filter(
                models.Source.state == models.State.NONE)
            qs = qs.filter(
                self.ENTITY_MODEL.selection == None)  # nopep8

        return qs
