# -*- coding: utf-8 -*-
# [SublimeLinter pep8-max-line-length:119]
# vim: set fileencoding=utf-8 :

import re
from urllib import parse

import bs4

from arroyo import exts

_BASE_DOMAIN = 'kat.cr'


class KickAss(exts.Origin):
    BASE_URL = 'http://{}/new/?page=1'.format(_BASE_DOMAIN)
    PROVIDER_NAME = 'kickass'

    _SIZE_TABLE = {
        'KB': 10 ** 3,
        'MB': 10 ** 6,
        'GB': 10 ** 9,
        'TB': 10 ** 12
    }

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
        selector = query.get('selector')
        if selector == 'episode':
            catstr = '%20category:tv'
            q = query.get('series', '')
        elif selector == 'movie':
            catstr = '%20category:movies'
            q = query.get('title', '')
        else:
            catstr = ''
            q = query.get('name') or \
                query.get('name-like', '').replace('%', ' ').replace('*', ' ')
            q = q.strip()

        if not q:
            return

        return ('http://{domain}/usearch/{q}{catstr}/?'
                'field=time_add&sorder=desc').format(
                    domain=_BASE_DOMAIN,
                    q=parse.quote(q),
                    catstr=catstr)

    def process_buffer(self, buff):
        """
        Finds referentes to sources in buffer.
        Returns a list with source infos
        """

        def process_row(row):
            try:
                name = row.select('a.cellMainLink')[0].text
            except IndexError:
                name = None

            try:
                uri = row.select('a.imagnet')[0].attrs['href']
            except (IndexError, AttributeError):
                uri = None

            try:
                size = row.select('td')[1].text.replace(' ', '')
                size = re.search(
                    r'([0-9\.]+)\s*([a-z]*)',
                    size,
                    re.IGNORECASE)
                amount = float(size.group(1))
                mod = self._SIZE_TABLE.get(size.group(2).upper(), 1)
                size = int(amount * mod)
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

            return {
                'name': name,
                'uri': uri,
                'size': size,
                'seeds': seeds,
                'leechers': leechers,
                'type': typ
            }

        soup = bs4.BeautifulSoup(buff)
        return map(process_row, soup.select('table.data tr')[1:])


__arroyo_extensions__ = [
    ('origin', 'kickass', KickAss)
]
