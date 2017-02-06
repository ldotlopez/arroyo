# -*- coding: utf-8 -*-


from arroyo import pluginlib
from arroyo.pluginlib import downloads


import asyncio
import re
from urllib import parse


import bs4
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

    def parse(self, buff, parser):
        soup = bs4.BeautifulSoup(buff, parser)
        table = soup.select_one('table.tlist')

        if table:
            return self.parse_listing(table)
        else:
            return self.parse_detail(soup)

    def parse_listing(self, block):
        def _parse(row):
            name = row.select_one('.tlistname a').text
            uri = self.normalize_uri(
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

    def get_torrent_file(self, uri):
        res = None

        @asyncio.coroutine
        def _task():
            nonlocal res
            res = yield from self.app.fetcher.fetch(uri)

        loop = asyncio.get_event_loop()
        loop.run_until_complete(_task())

        return downloads.magnet_from_torrent_data(res)

    def parse_detail(self, block):
        name = block.select_one('.content .container .viewtorrentname').text
        seeds = block.select_one('.content .container .viewsn').text
        leechers = block.select_one('.content .container .viewln').text
        links = block.select('.content .container a')
        links = [x.attrs.get('href', '') for x in links]
        links = [x for x in links if 'page=download' in x and 'txt=1' not in x]
        assert len(links) == 1

        uri = self.normalize_uri(links[0])
        uri = self.get_torrent_file(uri)
        return [{
            'name': name,
            'seeds': seeds,
            'leechers': leechers,
            'uri': uri
        }]

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

    def normalize_uri(self, uri):
        if uri.startswith('//'):
            uri = 'http:' + uri
        return uri

__arroyo_extensions__ = [
    Nyaa
]
