from arroyo import models
from arroyo.exts.queries import common


class Query(common.HighLevelQuery):
    HIGH_LEVEL_MODEL = models.Movie
    HIGH_LEVEL_ATTR = 'movie'
    SELECTION_MODEL = models.MovieSelection


__arroyo_extensions__ = [
    ('query', 'movie', Query)
]
