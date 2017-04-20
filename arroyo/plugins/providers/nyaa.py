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


from arroyo import (
    bittorrentlib,
    pluginlib
)


from urllib import parse


import humanfriendly
from appkit import uritools


class Nyaa(pluginlib.Provider):
    __extension_name__ = 'nyaa'

    DEFAULT_URI = 'https://www.nyaa.se/?sort=0&order=1'
    URI_PATTERNS = [
        r'^http(s)?://([^.]\.)?nyaa\.se/'
    ]

    def paginate(self, uri):
        parsed = parse.urlparse(uri)
        if parsed.path == '/':
            yield from uritools.paginate_by_query_param(uri, 'offset', 1)
        else:
            yield uri

    def get_query_uri(self, query):
        uri = 'https://www.nyaa.se/?page=search&cats=0_0&filter=0&term={q}'
        return uri.format(q=parse.quote(query.base_string))

    def parse(self, buff):
        try:
            header = buff[0:11].decode('utf-8')
        except UnicodeError:
            header = None

        # Input is torrent file
        if header == 'd8:announce':
            return self.parse_torrent_file(buff)

        soup = self.parse_buffer(buff)
        table = soup.select_one('table.tlist')
        if table:
            # Input is listing
            return self.parse_listing(table)
        else:
            # Input is detail
            return self.parse_detail(soup)

    def parse_listing(self, block):
        def _parse(row):
            name = row.select_one('.tlistname a').text
            uri = uritools.normalize(
                row.select_one('.tlistdownload a').attrs.get('href'))

            size = humanfriendly.parse_size(
                 row.select_one('.tlistsize').text)

            try:
                seeds = row.select_one('.tlistsn').text
            except AttributeError:
                seeds = None

            try:
                leechers = row.select_one('.tlistln').text
            except AttributeError:
                leechers = None

            return {
                'name': name,
                'uri': uri,
                'size': size,
                'seeds': seeds,
                'leechers': leechers
            }

        ret = [_parse(x) for x in block.select('tr.tlistrow')]
        ret = [x for x in ret if x]
        return ret

    def parse_detail(self, block):
        name = block.select_one('.content .container .viewtorrentname').text
        seeds = block.select_one('.content .container .viewsn').text
        leechers = block.select_one('.content .container .viewln').text
        links = block.select('.content .container a')
        links = [x.attrs.get('href', '') for x in links]
        links = [x for x in links if 'page=download' in x and 'txt=1' not in x]
        assert len(links) == 1

        uri = uritools.normalize(links[0])
        # uri = self.get_torrent_file(uri)
        return [{
            'name': name,
            'seeds': seeds,
            'leechers': leechers,
            'uri': uri
        }]

    def parse_torrent_file(self, buff):
        magnet = bittorrentlib.magnet_from_torrent_data(buff)
        parsed = parse.urlparse(magnet)
        qs = parse.parse_qs(parsed.query)

        return [{
            'name': qs['dn'][-1],
            'uri': magnet
        }]


__arroyo_extensions__ = [
    Nyaa
]
