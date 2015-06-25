# -*- coding: utf-8 -*-
# [SublimeLinter pep8-max-line-length:119]
# vim: set fileencoding=utf-8 :

from arroyo import (
    downloads,
    exts,
    models
)


class MockDownloader(exts.Downloader):
    _VARIABLES_NS = 'downloader.mock.states'

    def __init__(self, app):
        super().__init__(app)

    def add(self, source, **kwargs):
        self.app.variables.set(
            self.get_source_key(source),
            models.Source.State.INITIALIZING)

        source.state = models.Source.State.INITIALIZING

    def remove(self, urn):
        self.app.variables.reset(
            self.get_urn_key(urn))

    def list(self):
        idx = len(self._VARIABLES_NS) + 1
        return [var[idx:] for var in
                self.app.variables.children(self._VARIABLES_NS)]

        # idx = len(self._VARIABLES_NS) + 1
        # ret = []
        # for var in self.app.variables.children(self._VARIABLES_NS):
        #     urn = var[idx:]
        #     src = self.app.db.get(models.Source, urn=urn)
        #     ret.append(src)

        # return ret

    def translate_item(self, urn):
        try:
            return self.app.db.get(models.Source, urn=urn)
        except orm.exc.NoResultFound:
            return None

    def get_state(self, urn):
        try:
            return self.app.variables.get(
                self.get_urn_key(urn))
        except KeyError:
            return None

    def get_source_key(self, source):
        return '%s.%s' % (self._VARIABLES_NS, source.urn)

    def get_urn_key(self, urn):
        return '%s.%s' % (self._VARIABLES_NS, urn)

__arroyo_extensions__ = [
    ('downloader', 'mock', MockDownloader)
]
