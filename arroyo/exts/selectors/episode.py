import re


from sqlalchemy.sql import functions


from arroyo import (
    exts,
    models
)


class Selector(exts.Selector):
    def __init__(self, app):
        super(Selector, self).__init__(app)
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
    def quality_filter(x, regexp):
        return re.search(regexp, x.name, re.IGNORECASE)

    def select(self, **filters):
        # Get various parameters
        series = filters.pop('series')
        year = filters.pop('year', None)
        language = filters.pop('language', None)
        season = filters.pop('season', None)
        number = filters.pop('episode', None)
        quality = filters.pop('quality', None)

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
                regexp = r'\b' + quality + r'\b'
                srcs = filter(lambda x: self.quality_filter(x, regexp), srcs)

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
