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

    def __init__(self, app, **filters):
        super(Selector, self).__init__(app)
        self._filters = filters.copy()
        self._source_table = {}
        self.app.signals.connect('source-state-change',
                                 self._on_source_state_change)

    def _on_source_state_change(self, src):
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

    def select(self):
        # Get various parameters
        series = self._filters.get('series')
        year = self._filters.get('year', None)
        language = self._filters.get('language', None)
        season = self._filters.get('season', None)
        number = self._filters.get('episode', None)
        quality = self._filters.get('quality', None)

        if not series:
            raise exc.ArgumentError('series filter is required')

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

        # Strip episodes with a selection
        qs = self.app.db.session.query(models.Episode)
        qs = qs.filter(models.Episode.selection == None)  # nopep8
        qs = qs.filter(models.Episode.series.ilike(series))
        if year:
            qs = qs.filter(functions.coalesce(models.Episode.year, '') == year)
        if language:
            qs = qs.filter(models.Episode.language == language)
        if season:
            qs = qs.filter(functions.coalesce(models.Episode.season, '') == season)  # nopep8
        if number:
            qs = qs.filter(functions.coalesce(models.Episode.number, '') == number)  # nopep8

        for ep in qs:
            print("Sources for {} ({}) s{}e{}".format(
                ep.series,
                ep.year,
                ep.season,
                ep.number))

            srcs = ep.sources

            # Filter out by quality
            if quality:
                srcs = filter(lambda x: self.quality_filter(x, quality), srcs)

            # Put PROPER's first
            srcs = sorted(srcs, key=self.proper_sort)

            # print("Check {}: {} sources".format(ep, len(srcs)))
            # print("=>", repr(srcs))

            if srcs:
                self._source_table[srcs[0]] = ep
                yield srcs[0]


__arroyo_extensions__ = [
    ('selector', 'episode', Selector)
]