# -*- coding: utf-8 -*-
# [SublimeLinter pep8-max-line-length:119]
# vim: set fileencoding=utf-8 :

from itertools import chain
import re
from urllib import parse

import bs4
from ldotcommons import utils

from arroyo import exc, exts


class KickAssImporter(exts.Importer):
    BASE_URL = 'http://kickass.to/'
    _SIZE_TABLE = {'KB': 10 ** 3, 'MB': 10 ** 6, 'GB': 10 ** 9, 'TB': 10 ** 12}

    def search(self, search):
        selector = search.get('selector')
        if selector == 'episode':
            catstr = '%20category:tv'
            q = search.get('series')
        elif selector == 'movie':
            catstr = '%20category:movies'
            q = search.get('title')
        else:
            q = search.get('name')

        d = {
            'base': KickAssImporter.BASE_URL,
            'q': parse.quote(q),
            'catstr': catstr,
            'page': 1
        }

        while True:
            yield ('{base}usearch/{q}{catstr}/{page}/?'
                   'field=time_add&sorder=desc').format(**d)
            d['page'] += 1

    def url_generator(self, url=None):
        if not url:
            url = self.BASE_URL

        if not url.endswith('/'):
            url += '/'

        p = parse.urlparse(url)
        q = parse.parse_qs(p.query)
        if 'page' not in q:
            q['page'] = '1'

        while True:
            url = parse.urlunparse((
                p.scheme,
                p.netloc,
                p.path,
                p.params,
                parse.urlencode(q),
                p.fragment))
            q['page'] = str(int(q['page']) + 1)
            yield url

    def process(self, buff):
        """
        Finds referentes to sources in buffer.
        Returns a list with source infos
        """

        sources = []

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
            except IndexError:
                msg = 'Invalid markup (Are you trying to import main page? ' + \
                      'That is unsupported, try with "{suggestion}")'.format(
                          suggestion=self.BASE_URL + 'new/'
                      )
                raise exc.ProcessException(msg)

            if not(all([uri, name, size, seeds, leechers])):
                raise exc.ProcessException('Invalid markup')

            sources.append({
                'uri': uri,
                'name': name,
                'timestamp': ts,
                'size': size,
                'language': 'eng-US',
                'seeds': seeds,
                'leechers': leechers
            })

        return sources


__arroyo_extensions__ = [
    ('importer', 'kickass', KickAssImporter)
]
