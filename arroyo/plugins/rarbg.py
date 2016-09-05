# -*- coding: utf-8 -*-

import bs4
import asyncio
from urllib import parse

from arroyo import plugin


class Rarbg(plugin.Origin):
    DEFAULT_URI = 'https://rarbg.to/torrents.php'
    PROVIDER = 'rarbg'
    URI_PATTERNS = [
        r'^http(s)?://([^.]+\.)?rarbg.to.*',
    ]

    CATEGORY_TYPE_IDS = {
        'episode': ('18', '41', ),
        'movie': ('44', '45', ),
    }

    REQ_HEADERS = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Encoding': 'gzip, deflate, sdch, br',
        'Accept-Language': 'en,es;q=0.8,fr;q=0.6,ca;q=0.4',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'Host': 'rarbg.to',
        'Cookie': '',
        'Pragma': 'no-cache',
        'Upgrade-Insecure-Requests': '1',
        'Referer': 'https://rarbg.to',
        'User-Agent': ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) '
                       'AppleWebKit/537.36(KHTML, like Gecko), '
                       'Chrome/52.0.2743.116 Safari/537.36'),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._throttle = asyncio.Semaphore(5)

    def _build_url(self, path=None, query=None):
        parsed = parse.urlparse(self.DEFAULT_URI)
        return '{scheme}://{netloc}{path}?{query}'.format(
            scheme=parsed.scheme, netloc=parsed.netloc,
            path=path or parsed.path, query=parse.urlencode(query or {})
        )

    def paginate(self):
        yield from self.paginate_by_query_param(self.uri, 'page', default=1)

    def get_query_uri(self, query):
        selector = query.kind
        params = query.params

        if selector == 'episode':
            season = params.get('season', '')
            if season:
                season = 's{:02d}'.format(season)

            episode = params.get('episode', '')
            if episode:
                episode = 'e{:02d}'.format(episode)

            search_str = '{} {}{}'.format(params.get('series', ''), season, episode)
            search_params = {
                'search': search_str.strip(),
                'categories': ';'.join(self.CATEGORY_TYPE_IDS['episode'])
            }

        elif selector == 'movie':
            search_str = '{} {}'.format(params.get('title'), params.get('year'))
            search_params = {
                'search': search_str.strip(),
                'categories': ';'.join(self.CATEGORY_TYPE_IDS['movie'])
            }

        else:
            name = (params.get('name') or
                    params.get('name-glob') or
                    params.get('name-like') or
                    params.get('name-regexp') or '')
            qs = name.replace('%', ' ').replace('*', ' ').strip()
            search_params = {'search': qs, }

        return self._build_url(query=search_params)

    def set_spambot_cookie(self):
        # index = self.app.fetcher.fetch(self.DEFAULT_URI)
        self.REQ_HEADERS['Cookie'] = 'vDVPaqSe=r9jSB2Wk;skt=C4HVQe2a;LastVisit=1473097598;expla=1'

    @asyncio.coroutine
    def get_data(self):
        self.set_spambot_cookie()
        return super().get_data()

    def parse(self, buff):
        html = bs4.BeautifulSoup(buff, 'lxml')
        info = html.select_one('table.lista')
        if info:
            return self.parse_detailed(info)
        return self.parse_listing(html)

    def parse_listing(self, html):
        links = html.select('a[href^=/torrent/]')
        for link in links:
            path = link['href']
            self.add_process_task(self._build_url(path=path))
        return []

    def parse_detailed(self, table):

        def prop_rows(child):
            if type(child) is bs4.element.Tag:
                return child.name == 'tr'

        rows = list(filter(prop_rows, table.contents))

        return [{
            'name': rows[-1].select('td')[-1].text.strip(),
            'uri': table.select_one('a[href^=magnet]')['href'],
            'language': 'eng-us',
        }]

    @asyncio.coroutine
    def fetch(self, url):
        with (yield from self._throttle):
            yield from asyncio.sleep(1)
            return (yield from super().fetch(url, params={'headers': self.REQ_HEADERS}))


__arroyo_extensions__ = [
    ('rarbg', Rarbg)
]
