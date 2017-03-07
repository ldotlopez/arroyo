# -*- coding: utf-8 -*-


from arroyo import pluginlib
models = pluginlib.models


VARIABLES_NS = 'downloader.mock'


def key(urn):
    return '{}.{}'.format(VARIABLES_NS, urn)


class MockDownloader(pluginlib.Downloader):
    __extension_name__ = 'mock'

    def __init__(self, app):
        super().__init__(app)

    def add(self, source, **kwargs):
        self.app.variables.set(
            key(source.urn),
            dict(state=models.Source.State.INITIALIZING, info={}))

    def remove(self, urn):
        self.app.variables.reset(
            key(urn))

    def list(self):
        idx = len(VARIABLES_NS) + 1
        return [var[idx:] for var in
                self.app.variables.children(VARIABLES_NS)]

    def translate_item(self, urn):
        return self.app.db.get(models.Source, urn=urn)

    def _get(self, urn):
        return self.app.variables.get(key(urn))

    def _set_prop(self, urn, prop, value):
        d = self._get(urn)
        d[prop] = value
        self.app.variables.reset(key(urn))
        self.app.variables.set(key(urn), d)

    def get_state(self, urn):
        try:
            return self._get(urn)['state']
        except KeyError:
            return None

    def get_info(self, urn):
        try:
            return self._get(urn)['info']
        except KeyError:
            return None

    def _update_state(self, source, state):
        self._set_prop(source.urn, 'state', state)

    def _update_info(self, source, info):
        self._set_prop(source.urn, 'info', info)

__arroyo_extensions__ = [
    MockDownloader
]
