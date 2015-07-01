from itertools import chain


from arroyo import (
    exts,
    models
)


class Query(exts.Query):
    def matches(self, everything):
        qs = self.app.db.session.query(models.Movie)

        # Strip episodes with a selection
        if not everything:
            qs = qs.filter(models.Movie.selection == None)  # nopep8

        items, params = self.apply_filters(
            models.Movie,
            dict(self.params),
            (x for x in qs))

        items, params = self.apply_filters(
            models.Source,
            params,
            chain.from_iterable(x.sources for x in items))

        for k in params:
            msg = "Unknow filter {key}"
            msg = msg.format(key=k)
            self.app.logger.warning(msg)

        if params == self.params:
            return []

        return items

__arroyo_extensions__ = [
    ('query', 'movie', Query)
]


# class Query(exts.Query):
#     _SUPPORTED_Q = ('1080p', '720p', '480p', 'hdtv')
#     _SUPPORTED_Q_STRING = ", ".join([
#         "'{}'".format(x) for x in _SUPPORTED_Q
#     ])

#     def __init__(self, app, spec):
#         super().__init__(app, spec)
#         self._source_table = {}
#         self.app.signals.connect('source-state-change',
#                                  self._on_source_state_change)

#     def _on_source_state_change(self, sender, **kwargs):
#         src = kwargs['source']
#         if src not in self._source_table:
#             return

#         # Link src and episode
#         ep = self._source_table[src]
#         ep.selection = models.MovieSelection(source=src)
#         self.app.db.session.commit()
#         del(self._source_table[src])

#     @staticmethod
#     def quality_filter(x, quality):
#         info = guessit.guess_episode_info(x.name)
#         screen_size = info.get('screenSize', '').lower()
#         fmt = info.get('format', '').lower()

#         if quality != 'hdtv':
#             return quality == screen_size
#         else:
#             return not screen_size and fmt == 'hdtv'

#     def matches(self, everything):
#         # Get various parameters
#         title = self.spec.get('title')
#         year = self.spec.get('year')
#         language = self.spec.get('language')

#         # Basic checks
#         if not title:
#             raise exc.ArgumentError('title filter is required')

#         # Parse quality filter
#         quality = self.spec.get('quality', None)
#         if quality:
#             quality = quality.lower()
#             if quality not in self.__class__._SUPPORTED_Q:
#                 msg = (
#                     "quality '{quality}' not supported, "
#                     "only {supported_qualities} are supported"
#                 )
#                 msg = msg.format(
#                     quality=quality,
#                     supported_qualities=self.__class__._SUPPORTED_Q_STRING
#                 )
#                 raise exc.ArgumentError(msg)

#         qs = self.app.db.session.query(models.Movie)

#         # Strip episodes with a selection
#         if not everything:
#             qs = qs.filter(models.Movie.selection == None)  # nopep8

#         if title:
#             qs = qs.filter(models.Movie.title.ilike(title))

#         if year:
#             qs = qs.filter(models.Movie.year == year)

#         if language:
#             qs = qs.filter(models.Movie.language == language)

#         ret = []
#         for ep in qs:
#             srcs = ep.sources
#             if quality:
#                 srcs = filter(lambda x: self.quality_filter(x, quality), srcs)

#             ret += srcs

#             for src in srcs:
#                 self._source_table[src] = ep

#         return ret

#     def sort(self, srcs):
#         # https://wiki.python.org/moin/HowTo/Sorting#The_Old_Way_Using_the_cmp_Parameter
#         # def proper_sort(x):
#         #     # guessit property other contains 'Proper'
#         #     return re.search(
#         #         r'\b(PROPER|REPACK|FIX)\b',
#         #         x.name)

#         # def release_group_sort(x):
#         #     pass
#         #

#         # return sorted(srcs, key=self.proper_sort, reverse=True)

#         return srcs

__arroyo_extensions__ = [
    ('query', 'movie', Query)
]
