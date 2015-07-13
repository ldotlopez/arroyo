from arroyo import exts, models

"""Examples
For: Game Of Thrones S05E05 720p HDTV x264-0SEC[rarbg]
GuessIt found: {
    [1.00] "screenSize": "720p",
    [1.00] "type": "episode",
    [1.00] "season": 5,
    [1.00] "format": "HDTV",
    [0.70] "series": "Game Of Thrones",
    [1.00] "releaseGroup": "0SEC[rarbg]",
    [1.00] "videoCodec": "h264",
    [1.00] "episodeNumber": 5
}

For: True Detective S02E04 INTERNAL HDTV x264-BATV
GuessIt found: {
    [1.00] "episodeNumber": 4,
    [1.00] "releaseGroup": "BATV",
    [1.00] "type": "episode",
    [0.70] "series": "True Detective",
    [0.50] "title": "INTERNAL",
    [1.00] "season": 2,
    [1.00] "format": "HDTV",
    [1.00] "videoCodec": "h264"
}
"""


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
        screen_size = item.tag_dict.get('mediainfo.screenSize', '').lower()
        fmt = item.tag_dict.get('mediainfo.format', '').lower()

        # Check for plain HDTV (in fact it means no 720p or anything else)
        if self.value == 'hdtv':
            is_match = not screen_size and fmt == 'hdtv'

        else:
            is_match = self.value == screen_size

        return is_match

__arroyo_extensions__ = [
    ('filter', 'quality', Filter)
]
