# -*- coding: utf-8 -*-

from arroyo import pluginlib


class SourceQuery(pluginlib.Query):
    __extension_name__ = 'source'

    KIND = 'source'

    def get_query_set(self, session, everything):
        qs = session.query(pluginlib.models.Source)

        if not everything:
            # Weird equality but it's OK, read it trice
            qs = qs.filter(pluginlib.models.Source.state ==
                           pluginlib.models.State.NONE)

        return qs

__arroyo_extensions__ = [
    SourceQuery
]
