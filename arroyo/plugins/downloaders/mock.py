# -*- coding: utf-8 -*-


from arroyo import pluginlib
models = pluginlib.models


VARIABLES_NS = 'downloader.mock.states'


class MockDownloader(pluginlib.Downloader):
    __extension_name__ = 'mock'

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
        idx = len(VARIABLES_NS) + 1
        return [var[idx:] for var in
                self.app.variables.children(VARIABLES_NS)]

    def translate_item(self, urn):
        return self.app.db.get(models.Source, urn=urn)

    def get_state(self, urn):
        try:
            return self.app.variables.get(
                self.get_urn_key(urn))
        except KeyError:
            return None

    def get_source_key(self, source):
        return '%s.%s' % (VARIABLES_NS, source.urn)

    def get_urn_key(self, urn):
        return '%s.%s' % (VARIABLES_NS, urn)

    def _update_state(self, source, state):
        self.app.variables.set(self.get_source_key(source), state)


__arroyo_extensions__ = [
    MockDownloader
]
