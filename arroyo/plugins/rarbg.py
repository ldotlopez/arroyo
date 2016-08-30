# -*- coding: utf-8 -*-

import bs4
import asyncio
from urllib import parse

from arroyo import plugin
from ldotcommons import fetchers


class Rarbg(plugin.Origin):
    BASE_URL = 'https://rarbg.to/torrents.php'
    PROVIDER_NAME = 'rarbg'
    CATEGORY_TYPE_IDS = {
        'episode': ('18', '41', ),
        'movie': ('44', '45', ),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._throttle = asyncio.Semaphore(5)

    def _build_url(self, path=None, query=None):
        parsed = parse.urlparse(self.BASE_URL)
        return '{scheme}://{netloc}{path}?{query}'.format(
            scheme=parsed.scheme, netloc=parsed.netloc,
            path=path or parsed.path, query=parse.urlencode(query or {})
        )

    def paginate(self, url):
        yield from self.paginate_by_query_param(url, 'page', default=1)

    def get_query_url(self, query):
        selector = query.get('kind')

        if selector == 'episode':
            season = query.get('season', '')
            if season:
                season = 's{:02d}'.format(season)

            episode = query.get('episode', '')
            if episode:
                episode = 'e{:02d}'.format(episode)

            search_str = '{} {}{}'.format(query.get('series', ''), season, episode)
            search_params = {
                'search': search_str.strip(),
                'categories': ';'.join(self.CATEGORY_TYPE_IDS['episode'])
            }

        elif selector == 'movie':
            search_str = '{} {}'.format(query.get('title'), query.get('year'))
            search_params = {
                'search': search_str.strip(),
                'categories': ';'.join(self.CATEGORY_TYPE_IDS['movie'])
            }

        else:
            name = (query.get('name') or
                    query.get('name-glob') or
                    query.get('name-like') or
                    query.get('name-regexp') or '')
            qs = name.replace('%', ' ').replace('*', ' ').strip()
            search_params = {'search': qs, }

        return self._build_url(query=search_params)

    def parse(self, buff):
        html = bs4.BeautifulSoup(buff, "lxml")
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
        s = self.app.settings

        fetcher = fetchers.AIOHttpFetcher(
            logger=self.logger.getChild('fetcher'),
            **{
                k.replace('-', '_'): v
                for (k, v) in s.get('fetcher').items()
            })

        with (yield from self._throttle):
            yield from asyncio.sleep(1)
            return (yield from fetcher.fetch(url))


__arroyo_extensions__ = [
    ('rarbg', Rarbg)
]
