import itertools


from arroyo import exts, models


class Query(exts.Query):
    def __init__(self, app, spec):
        super().__init__(app, spec)

        self._known_srcs = set()
        self.app.signals.connect('source-state-change',
                                 self._on_source_state_change)

    def _on_source_state_change(self, sender, **kwargs):
        src = kwargs['source']
        if src not in self._known_srcs:
            return

        # Link src and episode
        ep = src.episode
        ep.selection = models.EpisodeSelection(source=src)
        self.app.db.session.commit()
        self._known_srcs.remove(src)

    def matches(self, everything):
        qs = self.app.db.session.query(models.Source).join(models.Episode)
        if not everything:
            qs = qs.filter(models.Episode.selection == None)  # nopep8

        items, params = self.apply_filters(
            qs, [models.Source, models.Episode], dict(self.params))

        for k in params:
            msg = "Unknow filter {key}"
            msg = msg.format(key=k)
            self.app.logger.warning(msg)

        if params == self.params:
            return []

        items, g = itertools.tee(items)
        self._known_srcs = set(list(g))

        return items


#
# Old stuff from previous architecture.
# Keep here as a reference
#

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
#         ep.selection = models.EpisodeSelection(source=src)
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
    ('query', 'episode', Query)
]
