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


from appkit import uritools


class Yts(pluginlib.Provider):
    __extension_name__ = 'yts'

    DEFAULT_URI = 'https://yts.ag/browse-movies'
    URI_PATTERNS = [
        r'^http(s)?://([^.]\.)?yts\.ag/'
    ]

    _TRACKERS = [
        'udp://glotorrents.pw:6969/announce',
        'udp://tracker.openbittorrent.com:80',
        'udp://tracker.coppersurfer.tk:6969',
        'udp://tracker.leechers-paradise.org:6969',
        'udp://p4p.arenabg.ch:1337',
        'udp://tracker.internetwarriors.net:1337']

    def paginate(self, uri):
        parsed = parse.urlparse(uri)
        if re.search(r'/browse-movies(/.+?/.+?/.+?/\d+?/.+)?$', parsed.path):
            yield from uritools.paginate_by_query_param(uri, 'page', 1)
        else:
            yield uri

    def get_query_uri(self, query):
        if query['type'] != 'movie':
            return None

        try:
            q = query['title']
        except KeyError:
            q = query.base_string.replace('*', ' ')

        q = q.strip()

        return 'https://yts.ag/browse-movies/{q}/all/all/0/latest'.format(
            q=parse.quote(q))

    def parse(self, buff):
        soup = self.parse_buffer(buff)
        detail_block = soup.select_one('#movie-content')

        if detail_block:
            return self.parse_detail(detail_block)
        else:
            return self.parse_listing(soup)

    def parse_listing(self, block):
        ret = []

        for movie in block.select('.browse-movie-wrap'):
            title = movie.select_one('.browse-movie-title')  # listings
            year = movie.select_one('.browse-movie-year')  # listings

            if not title or not year:
                continue

            title = title.text
            year = year.text

            for link in movie.select('a'):
                href = link.attrs.get('href', '')

                if '/torrent/download/' not in href:
                    continue

                ret.append(self.build_payload(
                    uri=href,
                    title=title,
                    year=year,
                    quality=link.text))

        return ret

    def parse_detail(self, block):
        ret = []

        title = block.select_one('#movie-info h1')
        year = block.select('#movie-info h2')[0]

        if not title or not year:
            return []

        title = title.text
        year = year.text

        links = [x for x in block.select('a')
                 if x.attrs.get('href', '').startswith('magnet:?')]

        for link in links:
            href = link.attrs['href']
            link_title = link.attrs.get('title', '')
            m = re.search(r'\s(\d+p) Magnet$', link_title, re.IGNORECASE)
            if m:
                quality = m.group(1)
            else:
                quality = None

            ret.append(self.build_payload(
                uri=href,
                title=title,
                year=year,
                quality=quality))

        return ret

    def build_payload(self, uri, title, year, quality=None):
        meta = {
            'movie.title': title,
            'movie.year': year
        }
        name = '{title} ({year})'.format(
            title=title,
            year=year)

        if quality:
            name += " {quality}".format(quality=quality)
            meta['mediainfo.quality'] = quality

        if not uri.startswith('magnet:?'):
            uri = self.convert_torrent_file_uri(uri)

        return {
            'language': 'eng-us',
            'type': 'movie',
            'name': name,
            'uri': uri,
            'meta': meta
        }

    def convert_torrent_file_uri(self, uri):
        m = re.search('/torrent/download/([0-9a-f]{40})$', uri, re.IGNORECASE)
        if m:
            magnet = 'magnet:?xt=urn:btih:{id}'.format(
                id=m.group(1).upper())

            for tr in self._TRACKERS:
                magnet = magnet + '&tr=' + parse.quote_plus(tr)

            return magnet

        else:
            raise ValueError(uri)

__arroyo_extensions__ = [
    Yts
]
