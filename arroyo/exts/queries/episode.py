import guessit
from arroyo import (
    exc,
    exts,
    models
)


class Query(exts.Query):
    _SUPPORTED_Q = ('1080p', '720p', '480p', 'hdtv')
    _SUPPORTED_Q_STRING = ", ".join([
        "'{}'".format(x) for x in _SUPPORTED_Q
    ])

    def __init__(self, app, spec):
        super().__init__(app, spec)
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
    def quality_filter(x, quality):
        info = guessit.guess_episode_info(x.name)
        screen_size = info.get('screenSize', '').lower()
        fmt = info.get('format', '').lower()

        if quality != 'hdtv':
            return quality == screen_size
        else:
            return not screen_size and fmt == 'hdtv'

    def matches(self, everything):
        # Get various parameters
        series = self.spec.get('series')
        year = self.spec.get('year')
        language = self.spec.get('language')
        season = self.spec.get('season')
        number = self.spec.get('episode')

        # Basic checks
        if not series:
            raise exc.ArgumentError('series filter is required')

        # Parse quality filter
        quality = self.spec.get('quality', None)
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

        # Strip episodes with a selection
        if not everything:
            qs = qs.filter(models.Episode.selection == None)  # nopep8

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

        ret = []
        for ep in qs:
            srcs = ep.sources
            if quality:
                srcs = filter(lambda x: self.quality_filter(x, quality), srcs)

            ret += srcs

            for src in srcs:
                self._source_table[src] = ep

        return ret

    def sort(self, srcs):
        # https://wiki.python.org/moin/HowTo/Sorting#The_Old_Way_Using_the_cmp_Parameter
        # def proper_sort(x):
        #     # guessit property other contains 'Proper'
        #     return re.search(
        #         r'\b(PROPER|REPACK|FIX)\b',
        #         x.name)

        # def release_group_sort(x):
        #     pass
        #

        # return sorted(srcs, key=self.proper_sort, reverse=True)

        return srcs

__arroyo_extensions__ = [
    ('query', 'episode', Query)
]
