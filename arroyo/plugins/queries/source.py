# -*- coding: utf-8 -*-

from arroyo import pluginlib
models = pluginlib.models


class SourceQuery(pluginlib.Query):
    __extension_name__ = 'source'

    KIND = 'source'

    def get_query_set(self, session, everything):
        qs = session.query(models.Source)

        if not everything:
            qs = qs.filter(models.Source.state == models.Source.State.NONE)

        return qs

__arroyo_extensions__ = [
    SourceQuery
]
