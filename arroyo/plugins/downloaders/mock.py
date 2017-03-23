# -*- coding: utf-8 -*-


from arroyo import pluginlib


models = pluginlib.models


VARIABLES_NS = 'downloader.mock'


def key(urn):
    return '{}.{}'.format(VARIABLES_NS, urn)


class MockDownloader(pluginlib.Downloader):
    __extension_name__ = 'mock'

    def __init__(self, app, *args, **kwargs):
        super().__init__(app, *args, **kwargs)
        self.variables = app.variables

    def add(self, source, **kwargs):
        self.variables.set(
            key(source.urn),
            {
                'state': models.Source.State.INITIALIZING,
                'info': {
                    'files': None,
                    'eta': None,
                    'progress': '0.0'
                }
            })

    def remove(self, urn):
        self.variables.reset(
            key(urn))

    def list(self):
        idx = len(VARIABLES_NS) + 1
        return [var[idx:] for var in
                self.variables.children(VARIABLES_NS)]

    def translate_item(self, urn, db):
        return db.get(models.Source, urn=urn)

    def _get_prop(self, urn, prop):
        return self.variables.get(key(urn))[prop]

    def _set_prop(self, urn, prop, value):
        data = self.variables.get(key(urn))
        data[prop] = value
        self.variables.reset(key(urn))
        self.variables.set(key(urn), data)

    def get_state(self, urn):
        try:
            return self._get_prop(urn, 'state')
        except KeyError:
            return None

    def get_info(self, urn):
        try:
            return self._get_prop(urn, 'info')
        except KeyError:
            return None

    def _update_state(self, source, state):
        self._set_prop(source.urn, 'state', state)

    def _update_info(self, source, info):
        src_info = self._get_prop(source.urn, 'info')
        src_info.update(info)
        src_info = {k: v for (k, v) in src_info.items() if v}

        self._set_prop(source.urn, 'info', src_info)


__arroyo_extensions__ = [
    MockDownloader
]
