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
        self._query = query
        self._source_table = {}
        self.app.signals.connect('source-state-change',
                                 self._on_source_state_change)

    def _on_source_state_change(self, sender, **kwargs):
        src = kwargs['source']
        if src not in self._source_table:
            return

        # Link src and episode
        ep = self._source_table[src]
        ep.selection = models.EpisodeSelection(source=src)
        self.app.db.session.commit()
        del(self._source_table[src])

    @staticmethod
    def proper_sort(x):
        return re.search(r'\b(PROPER|REPACK)\b', x.name) is None

    @staticmethod
    def quality_filter(x, quality):
        info = guessit.guess_episode_info(x.name)
        screen_size = info.get('screenSize', '').lower()
        fmt = info.get('format', '').lower()

        if quality != 'hdtv':
            return quality == screen_size
        else:
            return not screen_size and fmt == 'hdtv'

    def select(self, everything):
        # Get various parameters
        series = self._query.get('series')
        year = self._query.get('year')
        language = self._query.get('language')
        season = self._query.get('season')
        number = self._query.get('episode')

        # Basic checks
        if not series:
            raise exc.ArgumentError('series filter is required')

        # Parse quality filter
        quality = self._query.get('quality', None)
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

        qs = self.app.db.session.query(models.Episode)

        if series:
            qs = qs.filter(models.Episode.series.ilike(series))

        if year:
            qs = qs.filter(models.Episode.year == year)

        if language:
            qs = qs.filter(models.Episode.language == language)

        if season:
            qs = qs.filter(models.Episode.season == season)

        if number:
            qs = qs.filter(models.Episode.number == number)

        # Strip episodes with a selection
        if not everything:
            qs = qs.filter(models.Episode.selection == None)  # nopep8

        for ep in qs:
            srcs = ep.sources

            # Filter out by quality
            if not everything and quality:
                srcs = filter(lambda x: self.quality_filter(x, quality), srcs)

            # Put PROPER's first
            srcs = sorted(srcs, key=self.proper_sort)
            for src in srcs:
                self._source_table[src] = ep
                yield src

                if not everything:
                    break  # Go to the next episode

            # if srcs:
            #     self._source_table[srcs[0]] = ep
            #     yield srcs[0]


__arroyo_extensions__ = [
    ('selector', 'episode', Selector)
]
