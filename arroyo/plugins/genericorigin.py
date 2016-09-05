from arroyo import plugin

import re
from urllib import parse


class GenericOrigin(plugin.Origin):
    PROVIDER = 'generic'

    def __init__(self, app, *args, **kwargs):
        super().__init__(app, *args, **kwargs)
        self.logger = app.logger

    def parse(self, buff):
        buff = buff.decode('utf-8')

        magnets = []
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


__arroyo_extensions__ = [
    ('generic', GenericOrigin)
]
