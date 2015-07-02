from arroyo import models
from arroyo.exts.queries import common


class Query(common.HighLevelQuery):
    HIGH_LEVEL_MODEL = models.Episode
    HIGH_LEVEL_ATTR = 'episode'
    SELECTION_MODEL = models.EpisodeSelection


__arroyo_extensions__ = [
    ('query', 'episode', Query)
]
