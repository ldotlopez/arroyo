# -*- coding: utf-8 -*-

from arroyo import plugin
from arroyo import importer


from datetime import datetime
import collections
import functools
import re
import time
from urllib import parse


import bs4
import humanfriendly


class EliteTorrent(plugin.Origin):
    PROVIDER = 'elitetorrent'
    DEFAULT_URI = 'http://www.elitetorrent.net/descargas/'

    _SETTINGS_NS = "plugin.elitetorrent"

    _time_table = {
        'seg': 1,
        'min': 60,
        'hrs': 60*60,
        'd': 60*60*24,
        'sem': 60*60*24*7,
        'mes': 60*60*24*30,
        'an': 60*60*24*365
    }

    _categories = {
        'series': 'episode',
        'series vose': 'episode',
        'peliculas': 'movie',
        'peliculas microhd': 'movie',
        'peliculas hdrip': 'movie',
        'estrenos': 'movie'
    }

    _default_lang = 'spa-es'
    _langs = [
        'spa-es',
        'lat-es'
    ]

    @staticmethod
    @functools.lru_cache(maxsize=8)
    def re_cache(re_str):
        return re.compile(re_str)

    def paginate(self):
        if self.re_cache(r'/torrent/\d+/').search(self.uri):
            yield self.uri
            return

        parsed = parse.urlparse(self.uri)

        # Split paths and params from parsed URI
        tmp = [x for x in parsed.path.split('/') if x]
        paths = []
        params = collections.OrderedDict({
            'orden': 'fecha',
            'pag': 1
        })

        for c in tmp:
            if ':' in c:
                k, v = c.split(':', 1)
                params[k] = v
            else:
                paths.append(c)

        pag_n = params.pop('pag')
        try:
            pag_n = int(pag_n)
        except ValueError:
            pag_n = 1

        while True:
            params['pag'] = pag_n
            pag_n += 1

            parsed = parsed._replace(
                path='/'.join(
                    paths +
                    ['{}:{}'.format(k, v) for (k, v) in params.items()]
                )
            )

            yield parse.urlunparse(parsed)

    def get_query_uri(self, query):
        kind = query.kind
        params = query.params

        if params.get('language', None) not in self._langs:
            return

        if kind == 'episode':
            q = params.get('series')
            year = params.get('year', None)
            season = params.get('season', None)
            episode = params.get('episode', None)

            if year:
                q += ' ({year})'.format(year=year)

            if season and episode:
                q += ' {season}x{episode:02d}'.format(
                    season=season, episode=episode)

        elif kind == 'movie':
            q = params.get('title')
            if year:
                q += ' ({year})'.format(year)

        elif kind == 'source':
            q = params.get('name', None) or \
                params.get('name-like', None) or \
                params.get('name-glob', None)
            if q:
                q = q.replace('*', ' ')

        else:
            return

        if q:
            q = parse.quote_plus(q.lower().strip())
            return 'http://www.elitetorrent.net/busqueda/' + q

    def parse(self, buff):
        soup = bs4.BeautifulSoup(buff, "html.parser")
        info = soup.select_one('.info-tecnica')
        if info:
            return self.parse_detailed(soup)
        else:
            return self.parse_listing(soup)

    def parse_listing(self, soup):
        torrent_href_re = re.compile(r'(https?://(www.)?elitetorrent.net)?/torrent/\d+/')  # nopep8

        def parse_link(x):
            href = x.attrs.get('href', '')
            text = x.text

            if text == '' or href == '':
                return None

            if not torrent_href_re.search(href):
                return None

            if href[0] == '/':
                href = 'http://www.elitetorrent.net' + href

            return (text, href)

        # Filter and torrent links that point to this site.
        links = [parse_link(x) for x in soup.select('a')]
        links = [x for x in links if x]

        return [dict(name=name, uri=uri) for (name, uri) in links]

    def parse_detailed(self, soup):
        info = soup.select_one('.info-tecnica')
        name = soup.select_one('#box-ficha h2').text

        if '(vose)' in name.lower():
            lang = None
        else:
            lang = self._default_lang

        links = soup.select('.enlace_torrent')
        links = map(lambda x: x.attrs['href'], links)
        links = filter(lambda x: x.startswith('magnet:?'), links)
        try:
            uri = next(links)
        except StopIteration:
            return []

        details = {}
        needed_details = ['created', 'type', 'size']
        for ch in info.children:
            try:
                txt = ch.text.lower()
            except AttributeError:
                continue

            if txt == 'fecha':
                try:
                    tmp = datetime.strptime(ch.next_sibling.text, '%d-%m-%Y')
                    details['created'] = int(time.mktime(tmp.timetuple()))
                except ValueError:  # Sometime we can get things like
                                    # 'Hoy, 20:32'. It's simplier to just drop
                                    # it and go to defaults
                    details['created'] = None

            elif txt.startswith('categor'):
                cat = ch.next_sibling.text.lower()

                # Catch 'vose' categories
                if cat.endswith(' vose'):
                    lang = None

                details['type'] = self._categories.get(cat, None)
                if details['type'] is None:
                    msg = "Unknow category : '{category}'"
                    msg = msg.format(category=cat)
                    self.app.logger.warning(msg)

            elif txt.startswith('tama'):
                details['size'] = humanfriendly.parse_size(
                    ch.next_sibling.text)

            # Break this loop ASAP please.
            if all([x in details for x in needed_details]):
                break

        m = self.re_cache(r'semillas: (\d+) \| clientes: (\d+)').search(
            soup.select_one('.ppal').text.lower()
        )

        seeds = m.group(1) if m else None
        leechers = m.group(2) if m else None

        ret = {
            'name': name,
            'uri': uri,
            'language': lang,
            'seeds': seeds,
            'leechers': leechers,
        }
        ret.update(details)

        return [ret]

__arroyo_extensions__ = [
    ('elitetorrent', EliteTorrent)
]
