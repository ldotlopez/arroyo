import itertools


from arroyo import exts, models


class Query(exts.Query):
    def __init__(self, app, spec):
        super().__init__(app, spec)

        self._known_srcs = set()

        # Connect signal
        # Important note here: it's using weak=False.
        # With weak=True the signal will disconnect automatically when the
        # Query object goes out of scope.
        # Cavehead: we will keep the object in memory forever, it's not
        # important for one-shot applications like command line but for webapps
        # it will be a problem.
        self.app.signals.connect('source-state-change',
                                 self._on_source_state_change,
                                 weak=False)

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


__arroyo_extensions__ = [
    ('query', 'episode', Query)
]
