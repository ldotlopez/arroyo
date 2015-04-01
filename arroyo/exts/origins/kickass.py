# -*- coding: utf-8 -*-
# [SublimeLinter pep8-max-line-length:119]
# vim: set fileencoding=utf-8 :

from itertools import chain
import re
from urllib import parse

import bs4
from ldotcommons import utils

from arroyo import exc, exts


class KickAss(exts.Origin):
    BASE_URL = 'http://kickass.to/new/?page=1'
    _SIZE_TABLE = {'KB': 10 ** 3, 'MB': 10 ** 6, 'GB': 10 ** 9, 'TB': 10 ** 12}

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
                query.get('name_like', '').replace('%', ' ').replace('*', ' ')
            q = q.strip()

        if not q:
            return

        d = {
            'base': KickAss.BASE_URL,
            'q': parse.quote(q),
            'catstr': catstr,
        }
        return ('http://kickass.to/usearch/{q}{catstr}/?'
                'field=time_add&sorder=desc').format(**d)

    def process_buffer(self, buff):
        """
        Finds referentes to sources in buffer.
        Returns a list with source infos
        """

        sources = []
        typs = {
            'Movies': 'movie',
            'TV': 'episode'
            # 'Music': 'music',
            # 'Books': 'book'
        }

        soup = bs4.BeautifulSoup(buff)
        ts = utils.utcnow_timestamp()
        z = zip(soup.select('tr.odd'), soup.select('tr.even'))
        i = chain.from_iterable(z)
        for row in i:
            try:
                tds = row.findAll('td')

                name = row.select('a.cellMainLink')[0].text
                uri = row.select('a.imagnet')[0].attrs['href']
                size = tds[1].text.replace(' ', '')
                m = re.findall(r'([0-9\.]+)(.+)', size)[0]
                size = int(float(m[0]) * self._SIZE_TABLE[m[1]])
                seeds = tds[-2].text
                leechers = tds[-2].text

                m = re.findall(r'Posted by .+? in (.+?)\b', tds[0].text)
                if m:
                    typ = typs.get(m[0], None)

            except IndexError:
                msg = 'Invalid markup (Are you trying to import main page? ' + \
                      'That is unsupported, try with "{suggestion}")'.format(
                          suggestion=self.BASE_URL
                      )
                raise exc.ProcessException(msg)

            if not(all([uri, name, size, seeds, leechers])):
                raise exc.ProcessException('Invalid markup')

            sources.append({
                'uri': uri,
                'name': name,
                'timestamp': ts,
                'size': size,
                'seeds': seeds,
                'leechers': leechers,
                'type': typ
            })

        return sources


__arroyo_extensions__ = [
    ('origin', 'kickass', KickAss)
]
