# -*- coding: utf-8 -*-

from arroyo import plugin


import re
import time
from urllib import parse


import bs4


class SpanishtrackerOrigin(plugin.Origin):
    __extension_name__ = 'spanishtracker-origin'

    BASE_URL = 'http://www.spanishtracker.com/torrents.php?page=0'
    PROVIDER_NAME = 'spanishtracker'

    _SIZE_TABLE = {'K': 10 ** 3, 'M': 10 ** 6, 'G': 10 ** 9}
    _MAGNET_STR = (
        r'magnet:?xt=urn:btih:{hash_string}&dn={name}&'
        r'tr=http%3A%2F%2Fwww.spanishtracker.com%3A2710%2Fannounce&'
        r'tr=http%3A%2F%2Ftracker.openbittorrent.com%3A80%2Fannounce&'
        r'tr=http%3A%2F%2Ftracker.publicbt.com%3A80%2Fannounce&'
        r'tr=http%3A%2F%2Ftpb.tracker.prq.to%3A80%2Fannounce&'
        r'tr=http%3A%2F%2Ftracker.prq.to%3A80%2Fannounce&'
        r'tr=udp%3A%2F%2Ftracker.openbittorrent.com%3A80&'
        r'tr=udp%3A%2F%2Ftracker.publicbt.com%3A80&'
        r'tr=udp%3A%2F%2Ftracker.openbittorrent.com%3A80&'
        r'tr=udp%3A%2F%2Ftracker.ccc.de%3A80&'
        r'tr=udp%3A%2F%2Ftracker.istole.it%3A6969'
        )

    def paginate(self, url):
        yield from self.paginate_by_query_param(url, 'page', default=0)

    def get_query_url(self, query):
        if not query.get('language', '').startswith('spa-'):
            return

        selector = query.get('kind', 'source')
        if selector == 'episode':
            catstr = '7'
            q = query.get('series')

        elif selector == 'movie':
            catstr = '1'
            q = query.get('title')

        elif selector == 'source':
            catstr = ''
            q = query.get('name') or \
                query.get('name-glob') or \
                query.get('name-like') or \
                query.get('name-regexp') or ''
            q = q.replace('%', ' ').replace('*', ' ')
            q = q.strip()

        if not q:
            return

        url = ('{base}?category={category}&search={q}'
               '&active=1&order=data&by=DESC')

        return url.format(
            base=self.BASE_URL,
            category=catstr,
            q=q)

    def parse(self, buff):
        def parse_row(row):
            fields = row.findChildren('td')

            # Build name and URI
            try:
                name = fields[1].find('a').text
                hash_string = re.findall(
                    r'([0-9a-f]{40})',
                    fields[1].find('a')['href'],
                    re.IGNORECASE)[0]
            except IndexError:
                return None

            uri = self._MAGNET_STR.format(
                hash_string=hash_string,
                name=parse.quote_plus(name)
            )

            # Timestamp
            timestamp = int(time.mktime(time.strptime(fields[5].text,
                                                      '%d/%m/%Y')))

            # Size
            try:
                size = re.search('([0-9\.]+) ([GMK])B', fields[6].text)
                amount = float(size.group(1))
                mod = self._SIZE_TABLE[size.group(2)]
                size = int(amount*mod)
            except IndexError:
                size = None

            # Seeds
            try:
                seeds = int(fields[7].text)
            except ValueError:
                seeds = None

            # Leechers
            try:
                leechers = int(fields[8].text)
            except ValueError:
                leechers = None

            # Type
            typ = None
            if re.search(r'(cap\.|hdtv|temporada)', name, re.IGNORECASE):
                typ = 'episode'

            elif re.search(r'(dvd|blu(ray)?|dvd|cam)([\s\.]*(rip|screener)?)',
                           name,
                           re.IGNORECASE):
                typ = 'movie'

            # Language
            lang = 'spa'
            if re.search(r'(espa.+?l.+?castellano)', name, re.IGNORECASE):
                lang = 'spa-ES'
            elif re.search(r'\blatino\b', name, re.IGNORECASE):
                lang = 'spa-MX'

            return {
                'uri': uri,
                'name': name,
                'timestamp': timestamp,
                'size': size,
                'seeds': seeds,
                'leechers': leechers,
                'type': typ,
                'language': lang
            }

        soup = bs4.BeautifulSoup(buff, "html.parser")
        rows = [x for x in soup.select('tr')
                if len(x.findChildren('td')) == 11][1:]

        return map(parse_row, rows)


__arroyo_extensions__ = [
    SpanishtrackerOrigin
]
