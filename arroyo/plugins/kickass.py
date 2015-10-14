# -*- coding: utf-8 -*-

from arroyo import plugin


import re
from urllib import parse


import bs4
import humanfriendly
from ldotcommons import utils


class KickAss(plugin.Origin):
    _BASE_DOMAIN = 'kat.cr'
    BASE_URL = 'http://{}/new/?page=1'.format(_BASE_DOMAIN)
    PROVIDER_NAME = 'kickass'

    _TYPES = {
        'movies': 'movie',
        'tv': 'episode'
        # 'music': 'music',
        # 'books': 'book'
    }

    def __init__(self, *args, **kwargs):
        super(KickAss, self).__init__(*args, **kwargs)
        self._logger = self.app.logger.getChild('kickass-importer')

    def paginate(self, url):
        yield from self.paginate_by_query_param(url, 'page', default=1)

    def get_query_url(self, query):
        selector = query.get('kind')

        if selector == 'episode':
            series = query.get('series')
            if not series:
                return

            q = '{} category:tv'.format(series)

            season = query.get('season')
            if season:
                q += ' season:{}'.format(season)

            episode = query.get('episode')
            if episode:
                q += ' episode:{}'.format(episode)

        elif selector == 'movie':
            title = query.get('title', '')
            if not title:
                return

            q = '{} category:movies'.format(title)

        else:
            q = query.get('name') or \
                query.get('name-glob') or \
                query.get('name-like') or \
                query.get('name-regexp') or ''
            q = q.replace('%', ' ').replace('*', ' ')
            q = q.strip()

        if not q:
            return

        return ('http://{domain}/usearch/{q}/?'
                'field=time_add&sorder=desc').format(
                    domain=self._BASE_DOMAIN,
                    q=parse.quote(q))

    def process_buffer(self, buff):
        """
        Finds referentes to sources in buffer.
        Returns a list with source infos

        FIXME: If not results are found KAT show a more generic search with a
        warning:
            Your search «***» did not match any documents
        """

        def process_row(row):
            try:
                name = row.select('a.cellMainLink')[0].text
            except IndexError:
                name = None

            try:
                hrefs = (x.attrs.get('href') for x in row.select('a'))
                magnets = filter(lambda x: x.startswith('magnet:?'), hrefs)
                uri = list(magnets)[0]
            except (IndexError, AttributeError):
                uri = None

            try:
                size = row.select('td')[1].text.replace(' ', '')
                size = humanfriendly.parse_size(size)

            except (IndexError, ValueError):
                size = None

            try:
                seeds = int(row.select('td')[-2].text)
            except (IndexError, ValueError):
                seeds = None

            try:
                leechers = int(row.select('td')[-1].text)
            except (IndexError, ValueError):
                leechers = None

            try:
                lines = row.select('td')[0].text.split('\n')
                lines = filter(lambda x: x, lines)
                lines = map(lambda x: x.strip(), lines)
                section_text = list(lines)[-1]
                typ = re.search(
                    r'\bin\s*(\S+?)\b',
                    section_text,
                    re.IGNORECASE)

                # typ = re.search(
                #     r'Posted by .+? in (.+?)\b',
                #     row.select('td')[0].text,
                #     re.IGNORECASE)

                typ = typ.group(1).lower().strip()
                typ = self._TYPES.get(typ)
            except IndexError:
                typ = None

            try:
                _table = {
                    'sec': 1,
                    'min': 60,
                    'hour': 60*60,
                    'day': 60*60*24,
                    'week': 60*60*24*7,
                    'month': 60*60*24*30,
                    'year': 60*60*24*365,
                }
                created = row.select('td')[3].text
                m = re.search(r'(\d+).+(sec|min|hour|day|week|month|year)',
                              row.select('td')[3].text)
                amount = int(m.group(1))
                qual = m.group(2)
                created = utils.now_timestamp() - (amount*_table[qual])
            except IndexError:
                created = None

            return {
                'name': name,
                'uri': uri,
                'size': size,
                'seeds': seeds,
                'leechers': leechers,
                'type': typ,
                'created': created
            }

        soup = bs4.BeautifulSoup(buff, "html.parser")
        return map(process_row, soup.select('table.data tr')[1:])


__arroyo_extensions__ = [
    ('kickass', KickAss)
]
