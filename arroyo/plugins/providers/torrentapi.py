# -*- coding: utf-8 -*-

# json_extended format:
#
# {'category': 'TV Episodes',
#  'download': 'magnet:?xt=urn:btih:000000000000000000000000000000000000000000000000&dn=Westworld.S01E10.iNTERNAL.HDTV.x264-TURBO%5Brartv%5D&tr=http%3A%2F%2Ftracker.trackerfix.com%3A80%2Fannounce&tr=udp%3A%2F%2F9.rarbg.me%3A2710&tr=udp%3A%2F%2F9.rarbg.to%3A2710&tr=udp%3A%2F%2Fopen.demonii.com%3A1337%2Fannounce',  # nopep8
#  'episode_info': {'airdate': '2016-12-04',
#                   'epnum': '10',
#                   'imdb': 'tt0475784',
#                   'seasonnum': '1',
#                   'themoviedb': '63247',
#                   'title': 'The Bicameral Mind',
#                   'tvdb': '296762',
#                   'tvrage': '37537'},
#  'info_page': 'https://torrentapi.org/redirect_to_info.php?token=xxxxxxxxxx&p=x_x_x_x_x_x_x__xxxxxxxxxx',  # nopep8
#  'leechers': 6,
#  'pubdate': '2016-12-06 10:13:24 +0000',
#  'ranked': 1,
#  'seeders': 85,
#  'size': 583676381,
#  'title': 'Westworld.S01E10.iNTERNAL.HDTV.x264-TURBO[rartv]'}


from arroyo import pluginlib
from arroyo.pluginlib import downloads

import asyncio
import json
import time
from urllib import parse


import aiohttp
import arrow


class TorrentAPI(pluginlib.Provider):
    __extension_name__ = 'torrentapi'

    # URL structure:
    # https://torrentapi.org/apidocs_v2.txt
    # https://torrentapi.org/pubapi_v2.php?get_token=get_token

    DEFAULT_URI = r'http://torrentapi.org/pubapi_v2.php?mode=list'

    URI_PATTERNS = [
        r'^http(s)?://([^.]+.)?torrentapi\.org/pubapi_v2.php\?'
    ]

    TOKEN_URL = 'http://torrentapi.org/pubapi_v2.php?get_token=get_token'
    SEARCH_URL = r'http://torrentapi.org/pubapi_v2.php?mode=search'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.token = None
        self.token_ts = 0
        self.token_last_use = 0

    @asyncio.coroutine
    def fetch(self, fetcher, uri):
        yield from self.refresh_token()

        uri = downloads.set_query_params(
            uri,
            format='json_extended',
            limit=100,
            sort='last',
            token=self.token)

        return (yield from super().fetch(fetcher, uri))

    @asyncio.coroutine
    def refresh_token(self):
        # Refresh token if it's older than 15M
        if time.time() - self.token_ts >= 15*60:
            conn = aiohttp.TCPConnector(verify_ssl=False)
            client = aiohttp.ClientSession(connector=conn)
            resp = yield from client.get(self.TOKEN_URL)
            buff = yield from resp.content.read()
            yield from resp.release()
            yield from client.close()

            self.token = json.loads(buff.decode('utf-8'))['token']
            self.token_ts = time.time()
            self.token_last_use = None
            return

        # No need to throttle
        if self.token_last_use is None:
            return

        # throttle
        now = time.time()
        since_last_use = self.token_last_use - now
        if since_last_use < 2:
            yield from asyncio.sleep(2 - since_last_use)

    def parse(self, buff):
        def convert_data(e):
            return {
                'name': e.get('title') or e.get('filename'),
                'uri': e['download'],
                'created': self.parse_created(e.get('pubdate', None)),
                'seeds': e.get('seeds', None),
                'leechers': e.get('leechers', None),
                'size': e.get('size', None),
                'type': self.parse_category(e['category'])
            }

        data = json.loads(buff.decode('utf-8'))
        try:
            psrcs = data['torrent_results']
        except KeyError:
            return []

        ret = [convert_data(x) for x in psrcs]
        return ret

    def get_query_uri(self, query):
        _category_table = {
            'episode': 'tv',
            'movie': 'movies'
        }

        q = {
            'search_string': query.base_string
        }

        if query.kind in _category_table:
            q['category'] = _category_table[query.kind]

        q['search_string'] = query.base_string
        return self.SEARCH_URL + "&" + parse.urlencode(q)

    @classmethod
    def parse_category(cls, category):
        if not category:
            return None

        if 'movie' in category.lower():
            return 'movie'

        elif 'episodes' in category.lower():
            return 'episode'

        return None

    @classmethod
    def parse_created(cls, created):
        if not created:
            return None

        return arrow.get(created[0:19]).to('local').timestamp


__arroyo_extensions__ = [
    TorrentAPI
]
