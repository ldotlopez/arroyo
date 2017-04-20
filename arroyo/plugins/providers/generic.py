# -*- coding: utf-8 -*-

# Copyright (C) 2015 Luis López <luis@cuarentaydos.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301,
# USA.


from arroyo import pluginlib


import re
from urllib import parse


from appkit import logging


class Provider(pluginlib.Provider):
    __extension_name__ = 'generic'

    DEFAULT_URI = None

    # URI_PATTERNS is not defined because we implement Provider.compatible_uri
    # method

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(self.__extension_name__)

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
        return False

__arroyo_extensions__ = [
    Provider
]
