from arroyo import pluginlib

import re
from urllib import parse


class Provider(pluginlib.Provider):
    __extension_name__ = 'generic'

    DEFAULT_URI = None

    # URI_PATTERNS is not defined because we implement Provider.compatible_uri
    # method

    def __init__(self, app, *args, **kwargs):
        super().__init__(app, *args, **kwargs)
        self.logger = app.logger

    def parse(self, buff, parser):
        buff = buff.decode('utf-8')

        matches = re.findall(
            r'(magnet:\?[-a-zA-Z0-9@:%_\+.~#?&//=;]+)',
            buff,
            re.IGNORECASE)

        ret = []
        for m in matches:
            parsed = parse.urlparse(m)
            qs = parse.parse_qs(parsed.query)
            try:
                ret.append(dict(
                    name=qs['dn'][-1],
                    uri=m
                ))
            except (KeyError, IndexError):
                msg = "Parameter «dn» not found in magnet link '{uri}'"
                msg = msg.format(uri=m)
                self.logger.warning(msg)
                pass

        return ret

    def compatible_uri(self, uri):
        return FALSE

__arroyo_extensions__ = [
    Provider
]
