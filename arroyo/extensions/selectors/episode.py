
import re
from ldotcommons import utils
from sqlalchemy.sql import functions


from arroyo.app import app
from arroyo import models


@app.register('selector', 'episode')
class Selector:
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
        qs = app.db.session.query(models.Episode)
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
                yield (srcs[0], ep)

    def post_download(self, src, ep):
        ep.selection = models.EpisodeSelection(source=src)
        app.db.session.commit()

# def download_episodes(**filters):
#     def proper_sort(x):
#         return re.search(r'\b(PROPER|REPACK)\b', x.name) is None

#     def quality_filter(x):
#         return re.search(regexp, x.name, re.IGNORECASE)

#     qs = app.db.session.query(models.Episode)
#     qs = qs.filter(models.Episode.selection == None)  # nopep8

#     series = filters.pop('series')
#     year = filters.pop('year', None)
#     language = filters.pop('language', None)
#     season = filters.pop('season', None)
#     quality = filters.pop('quality', None)

#     qs = qs.filter(models.Episode.series.ilike(series))
#     if year:
#         qs = qs.filter(functions.coalesce(models.Episode.year, '') == year)
#     if language:
#         qs = qs.filter(models.Episode.language == language)
#     if season:
#         qs = qs.filter(functions.coalesce(models.Episode.season, '') == season)

#     for ep in qs:
#         srcs = ep.sources

#         # Filter out by quality
#         if quality:
#             regexp = r'\b' + quality + r'\b'
#             srcs = filter(quality_filter, srcs)

#         # Put PROPER's first
#         srcs = sorted(srcs, key=proper_sort)

#         try:
#             src = srcs[0]
#         except IndexError:
#             print("No sources for {}".format(ep))
#             continue

#         print("Check {}: {} sources".format(ep, len(srcs)))

#         # Once src is added into Downloader link ep and src
#         app.downloader.add(src)

#         ep.selection = models.EpisodeSelection(source=srcs[0])
#         app.db.session.commit()