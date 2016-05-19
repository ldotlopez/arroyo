# -*- coding: utf-8 -*-

from arroyo import plugin

from datetime import datetime
import re
import time

import bs4
import humanfriendly
from ldotcommons import utils


class EliteTorrent(plugin.Origin):
    BASE_URL = 'http://www.elitetorrent.net/categoria/2/peliculas/modo:listado'
    PROVIDER_NAME = 'elitetorrent'

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
        'peliculas': 'movie'
    }

    def paginate(self, url):
        if re.search(r'/torrent/\d+/'):
            yield url
        else:
            yield url

    def get_query_url(self, query):
        return None

    def parse(self, buff):
        soup = bs4.BeautifulSoup(buff, "html.parser")
        info = soup.select_one('.info-tecnica')
        if info:
            return self.parse_detailed(soup)
        else:
            return self.parse_listing(soup)

    def parse_listing(self, soup):
        def parse_row(row):
            r = {
                'name': row.select_one('a.nombre').text,
                'uri': None,
                'size': None,
                'seeds': None,
                'leechers': None,
                'type': None,
                'created': None
            }

            r['href'] = (
                'http://www.elitetorrent.net/' +
                row.select_one('a.icono-bajar').attrs['href']
            )

            try:
                r['seeds'] = int(row.select_one('td.semillas').text)
            except ValueError:
                pass

            try:
                r['leechers'] = int(row.select_one('td.clientes').text)
            except ValueError:
                pass

            created = row.select_one('td.fecha').text
            m = re.search(r'^Hace (.+?) (seg|min|hrs|d|sem|mes|an)', created)
            if m:
                amount = m.group(1)
                amount = 1 if amount.startswith('un') else int(amount)
                qual = m.group(2)

                if qual in self._time_table:
                    created = \
                        utils.now_timestamp() - self._time_table[qual] * amount
                    r['created'] = created

            return r

        rows = soup.select('table.fichas-listado tr')[1:]

        return list(map(parse_row, rows))

    def parse_detailed(self, soup):
        info = soup.select_one('.info-tecnica')
        name = soup.select_one('#box-ficha h2').text

        if '(vose)' in name.lower():
            lang = None
        else:
            lang = 'esp-es'

        links = soup.select('.enlace_torrent')
        links = map(lambda x: x.attrs['href'], links)
        links = filter(lambda x: x.startswith('magnet:?'), links)
        try:
            uri = next(links)
        except StopIteration:
            return []

        for ch in info.children:
            try:
                txt = ch.text
            except AttributeError:
                continue

            if txt.lower() == 'fecha':
                created = datetime.strptime(ch.next_sibling.text, '%d-%m-%Y')
                created = int(time.mktime(created.timetuple()))

            elif txt.lower().startswith('categor'):
                cat = ch.next_sibling.text.lower()
                type = self._categories.get(cat, None)

            elif txt.lower().startswith('tama'):
                size = humanfriendly.parse_size(ch.next_sibling.text)

        m = re.search(r'semillas: (\d+) \| clientes: (\d+)',
                      soup.select_one('.ppal').text.lower())
        if m:
            seeds = m.group(1)
            leechers = m.group(2)

        return [{
            'name': name,
            'uri': uri,
            'size': size,
            'type': type,
            'language': lang,
            'seeds': seeds,
            'leechers': leechers
        }]


__arroyo_extensions__ = [
    ('elitetorrent', EliteTorrent)
]
