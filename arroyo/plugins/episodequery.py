# -*- coding: utf-8 -*-

from arroyo import plugin
from arroyo.plugin.tools import query


class Query(query.HighLevelQuery):
    HIGH_LEVEL_MODEL = plugin.models.Episode
    HIGH_LEVEL_ATTR = 'episode'
    SELECTION_MODEL = plugin.models.EpisodeSelection


__arroyo_extensions__ = [
    ('episode', Query)
]
