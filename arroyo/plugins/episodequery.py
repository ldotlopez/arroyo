# -*- coding: utf-8 -*-

from arroyo import plugin
from arroyo.plugin.tools import query


class EpisodeQuery(query.HighLevelQuery):
    __extension_name__ = 'episode-query'

    ENTITY_MODEL = plugin.models.Episode
    ENTITY_ATTR = 'episode'
    SELECTION_MODEL = plugin.models.EpisodeSelection


__arroyo_extensions__ = [
    EpisodeQuery
]
