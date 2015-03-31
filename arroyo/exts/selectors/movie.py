import re


import guessit
from sqlalchemy.sql import functions


from arroyo import (
    exc,
    exts,
    models
)


class Selector(exts.Selector):
    _SUPPORTED_Q = ('1080p', '720p', '480p', 'hdtv')
    _SUPPORTED_Q_STRING = ", ".join([
        "'{}'".format(x) for x in _SUPPORTED_Q
    ])

    def __init__(self, app, query):
        super(Selector, self).__init__(app)
        self._query = query.copy()
        self._source_table = {}
        self.app.signals.connect('source-state-change',
                                 self._on_source_state_change)

    def _on_source_state_change(self, sender, **kwargs):
        src = kwargs['source']
        if src not in self._source_table:
            return

        # Link src and Movie
        mov = self._source_table[src]
        mov.selection = models.MovieSelection(source=src)
        self.app.db.session.commit()
        del(self._source_table[src])

    @staticmethod
    def proper_sort(x):
        return re.search(r'\b(PROPER|REPACK)\b', x.name) is None

    @staticmethod
    def quality_filter(x, quality):
        info = guessit.guess_movie_info(x.name)
        screen_size = info.get('screenSize', '').lower()
        fmt = info.get('format', '').lower()

        if quality != 'hdtv':
            return quality == screen_size
        else:
            return not screen_size and fmt == 'hdtv'

    def select(self, everything):
        if not self._query.get('title'):
            raise exc.ArgumentError('title filter is required')

        # Get various parameters
        title = self._query.get('title')
        year = self._query.get('year')
        language = self._query.get('language')

        quality = self._query.get('quality')
        if quality:
            quality = quality.lower()
            if quality not in self.__class__._SUPPORTED_Q:
                msg = (
                    "quality '{quality}' not supported, "
                    "only {supported_qualities} are supported"
                )
                msg = msg.format(
                    quality=quality,
                    supported_qualities=self.__class__._SUPPORTED_Q_STRING
                )
                raise exc.ArgumentError(msg)

        # Strip movies with a selection
        qs = self.app.db.session.query(models.Movie)

        if title:
            qs = qs.filter(models.Movie.title.ilike(title))

        if year:
            qs = qs.filter(functions.coalesce(models.Movie.year, '') == year)

        if language:
            qs = qs.filter(
                functions.coalesce(
                    models.Movie.language, 'eng-us') == language)

        if not everything:
            qs = qs.filter(models.Movie.selection == None)  # nopep8

        for mov in qs:
            srcs = mov.sources

            # Filter out by quality
            if quality:
                srcs = filter(lambda x: self.quality_filter(x, quality), srcs)

            # Put PROPER's first
            srcs = sorted(srcs, key=self.proper_sort)
            for src in srcs:
                self._source_table[src] = mov
                yield src

                if not everything:
                    break  # Go to the next title


__arroyo_extensions__ = [
    ('selector', 'movie', Selector)
]
