# -*- coding: utf-8 -*-

from arroyo import plugin
from arroyo.plugin.tools import query


class Query(query.HighLevelQuery):
    ENTITY_MODEL = plugin.models.Episode
    ENTITY_ATTR = 'episode'
    SELECTION_MODEL = plugin.models.EpisodeSelection


__arroyo_extensions__ = [
    ('episode', Query)
]
