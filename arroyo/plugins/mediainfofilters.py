# -*- coding: utf-8 -*-

from arroyo import plugin
models = plugin.models


class QualityFilter(plugin.Filter):
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
        screen_size = item.tag_dict.get('mediainfo.screen_size', '').lower()
        fmt = item.tag_dict.get('mediainfo.format', '').lower()

        # Check for plain HDTV (in fact it means no 720p or anything else)
        if self.value == 'hdtv':
            is_match = not screen_size and fmt == 'hdtv'

        else:
            is_match = self.value == screen_size

        return is_match


class CodecFilter(plugin.Filter):
    APPLIES_TO = models.Source
    HANDLES = ('codec',)

    def __init__(self, app, key, value):
        super().__init__(app, key, value.lower())

    def filter(self, item):
        return (
            self.value ==
            item.tag_dict.get('mediainfo.video_codec', '').lower())


__arroyo_extensions__ = [
    ('quality', QualityFilter),
    ('codec', CodecFilter)
]
