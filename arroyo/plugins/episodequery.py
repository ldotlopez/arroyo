# -*- coding: utf-8 -*-

from arroyo.plugin import (
    models,
    querytools
)


class Query(querytools.HighLevelQuery):
    HIGH_LEVEL_MODEL = models.Episode
    HIGH_LEVEL_ATTR = 'episode'
    SELECTION_MODEL = models.EpisodeSelection


__arroyo_extensions__ = [
    ('episode', Query)
]
