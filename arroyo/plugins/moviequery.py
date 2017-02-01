# -*- coding: utf-8 -*-

from arroyo import plugin
from arroyo.plugin.tools import query


class MovieQuery(query.HighLevelQuery):
    KIND = 'movie'
    ENTITY_MODEL = plugin.models.Movie
    ENTITY_ATTR = 'movie'
    SELECTION_MODEL = plugin.models.MovieSelection


__arroyo_extensions__ = [
    ('movie', MovieQuery)
]
