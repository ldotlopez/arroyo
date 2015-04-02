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

        failures = 0

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
                seeds = int(tds[-2].text)
                leechers = int(tds[-1].text)

                m = re.findall(r'Posted by .+? in (.+?)\b', tds[0].text)
                if m:
                    typ = typs.get(m[0], None)

            except IndexError as e:
                if failures < 3:
                    msg = 'Incorrect markup found on one row, continuing with remaining data'
                    self._logger.warning(msg)
                    failures += 1
    
                if failures == 3:
                    self._logger.warning('Too many failures, ignoring future warnings')
    
                continue

            sources.append({
                'uri': uri,
                'name': name,
                'size': size,
                'seeds': seeds,
                'leechers': leechers,
                'timestamp': ts,
                'type': typ
            })

            # src = {
            #     'uri': uri,
            #     'name': name,
            #     'size': size,
            #     'seeds': seeds,
            #     'leechers': leechers
            # }
            # for k in src:
            #     if src[k] is None and src[k] != 0:
            #         msg = 'Missing mandatory field \'{key}\''
            #         msg = msg.format(key=k)
            #         raise exc.ProcessException(msg, row=row, buffer=buff)
            #
            # src.update({
            #     'timestamp': ts,
            #     'type': typ
            # })

        if not sources:
            msg = ('Invalid markup (Are you trying to import main page? '
                   'That\'s unsupported, try with "{suggestion}")')
            msg = msg.format(suggestion=self.BASE_URL)
            raise exc.ProcessException(msg, buffer=buff)

        return sources


__arroyo_extensions__ = [
    ('origin', 'kickass', KickAss)
]
