# -*- coding: utf-8 -*-

from arroyo import plugin
models = plugin.models


class MockDownloader(plugin.Downloader):
    __extension_name__ = 'mock'

    _VARIABLES_NS = 'downloader.mock.states'

    def __init__(self, app):
        super().__init__(app)

    def add(self, source, **kwargs):
        self.app.variables.set(
            self.get_source_key(source),
            models.Source.State.INITIALIZING)

    def remove(self, urn):
        self.app.variables.reset(
            self.get_urn_key(urn))

    def list(self):
        idx = len(self._VARIABLES_NS) + 1
        return [var[idx:] for var in
                self.app.variables.children(self._VARIABLES_NS)]

    def translate_item(self, urn):
        return self.app.db.get(models.Source, urn=urn)

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

    def _update_state(self, source, state):
        self.app.variables.set(self.get_source_key(source), state)


__arroyo_extensions__ = [
    MockDownloader
]
