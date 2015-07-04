import guessit

from arroyo import exts, models


class Filter(exts.Filter):
    APPLIES_TO = models.Source
    HANDLES = ('quality',)

    _SUPPORTED = ('1080p', '720p', '480p', 'hdtv')
    _SUPPORTED_STR = ", ".join("'{}'".format(x) for x in _SUPPORTED)

    def __init__(self, app, key, value):
        value = value.lower()

        if value not in self._SUPPORTED:
            msg = ("Quality '{quality}' not supported, "
                   "only {supported_qualities} are supported")

            msg = msg.format(
                quality=value,
                supported_qualities=self._SUPPORTED_STR)

            raise ValueError(msg)

        super().__init__(app, key, value)

    def filter(self, item):
        info = guessit.guess_episode_info(item.name)
        screen_size = info.get('screenSize', '').lower()
        fmt = info.get('format', '').lower()

        if self.value != 'hdtv':
            return self.value == screen_size
        else:
            return not screen_size and fmt == 'hdtv'


__arroyo_extensions__ = [
    ('filter', 'quality', Filter)
]
