# -*- coding: utf-8 -*-

from arroyo import plugin
from arroyo.plugin.tools import query


class Query(query.HighLevelQuery):
    HIGH_LEVEL_MODEL = plugin.models.Movie
    HIGH_LEVEL_ATTR = 'movie'
    SELECTION_MODEL = plugin.models.MovieSelection


__arroyo_extensions__ = [
    ('movie', Query)
]
