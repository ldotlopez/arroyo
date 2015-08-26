from arroyo.plugin import querytools
from arroyo import models


class Query(querytools.HighLevelQuery):
    HIGH_LEVEL_MODEL = models.Episode
    HIGH_LEVEL_ATTR = 'episode'
    SELECTION_MODEL = models.EpisodeSelection


__arroyo_extensions__ = [
    ('episode', Query)
]
