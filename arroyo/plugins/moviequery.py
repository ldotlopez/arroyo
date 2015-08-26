from arroyo.plugin import querytools
from arroyo import models


class Query(querytools.HighLevelQuery):
    HIGH_LEVEL_MODEL = models.Movie
    HIGH_LEVEL_ATTR = 'movie'
    SELECTION_MODEL = models.MovieSelection


__arroyo_extensions__ = [
    ('movie', Query)
]
