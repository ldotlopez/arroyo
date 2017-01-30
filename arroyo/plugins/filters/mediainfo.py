# -*- coding: utf-8 -*-

from arroyo import pluginlib
models = pluginlib.models


class CodecFilter(pluginlib.IterableFilter):
    __extension_name__ = 'codec'

    APPLIES_TO = models.Source
    HANDLES = ['codec']

    def filter(self, key, value, item):
        item_video_codec = item.tag_dict.get('mediainfo.video_codec', '')
        return (value == item_video_codec.lower())


class QualityFilter(pluginlib.IterableFilter):
    __extension_name__ = 'quality'

    APPLIES_TO = models.Source
    HANDLES = ['quality']

    _SUPPORTED = ('1080p', '720p', '480p', 'hdtv')
    _SUPPORTED_STR = ", ".join("'{}'".format(x) for x in _SUPPORTED)

    def filter(self, key, value, item):
        value = value.lower()

        if value not in self._SUPPORTED:
            msg = ("Quality '{quality}' not supported, "
                   "only {supported_qualities} are supported")

            msg = msg.format(
                quality=value,
                supported_qualities=self._SUPPORTED_STR)

            raise ValueError(msg)

        screen_size = item.tag_dict.get('mediainfo.screen_size', '').lower()
        fmt = item.tag_dict.get('mediainfo.format', '').lower()

        # Check for plain HDTV (in fact it means no 720p or anything else)
        if value == 'hdtv':
            is_match = not screen_size and fmt == 'hdtv'

        else:
            is_match = value == screen_size

        return is_match


__arroyo_extensions__ = [
    CodecFilter,
    QualityFilter
]
