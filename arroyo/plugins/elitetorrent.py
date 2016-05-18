# -*- coding: utf-8 -*-

from arroyo import plugin

import re


import bs4
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

    def paginate(self, url):
        # yield from self.paginate_by_query_param(url, 'page', default=0)
        yield url

    def get_query_url(self, query):
        return None

    def parse(self, buff):
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

        soup = bs4.BeautifulSoup(buff, "html.parser")
        rows = soup.select('table.fichas-listado tr')[1:]

        return list(map(parse_row, rows))

__arroyo_extensions__ = [
    ('elitetorrent', EliteTorrent)
]
