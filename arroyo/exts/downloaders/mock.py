# -*- coding: utf-8 -*-
# [SublimeLinter pep8-max-line-length:119]
# vim: set fileencoding=utf-8 :

from arroyo import (exts, models)


class MockDownloader(exts.Downloader):
    _VARIABLES_NS = 'downloader.mock.states'

    def __init__(self, app):
        super().__init__(app)

    def add(self, source, **kwargs):
        self.app.variables.set(
            self.get_source_key(source),
            models.Source.State.INITIALIZING)

        source.state = models.Source.State.INITIALIZING

    def remove(self, source):
        self.app.variables.reset(
            self.get_source_key(source))

    def list(self):
        idx = len(self._VARIABLES_NS) + 1
        ret = []
        for var in self.app.variables.children(self._VARIABLES_NS):
            urn = var[idx:]
            src = self.app.db.get(models.Source, urn=urn)
            ret.append(src)

        return ret

    def translate_item(self, source):
        return source

    def get_state(self, source):
        return self.app.variables.get(
            self.get_source_key(source))

    def get_source_key(self, source):
        return '%s.%s' % (self._VARIABLES_NS, source.urn)

    def update_source_state(self, source, state):
        k = self.get_source_key(source)
        try:
            self.app.variables.get(k)
        except KeyError:
            raise KeyError(source)

        self.variables.set(k, state)

__arroyo_extensions__ = [
    ('downloader', 'mock', MockDownloader)
]
