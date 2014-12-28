# -*- coding: utf-8 -*-
# [SublimeLinter pep8-max-line-length:119]
# vim: set fileencoding=utf-8 :

import re
import time

import bs4
import feedparser
from ldotcommons.utils import utcnow_timestamp

from arroyo.app import app


@app.register('importer', 'tpb')
class TpbImporter:
    BASE_URL = 'http://thepiratebay.com/recent/0/'

    _SIZE_TABLE = {'K': 10 ** 3, 'M': 10 ** 6, 'G': 10 ** 9}

    def url_generator(self, url=None):
        if url is None:
            url = self.BASE_URL

        # And '/' at the end
        if not url.endswith('/'):
            url += '/'

        # Get page
        try:
            page = int(re.findall(r'/(\d+)/', url)[0])
        except IndexError:
            page = 0
            url += '0/'

        pre, post = re.split(r'/\d+/', url, maxsplit=1)

        while True:
            yield pre + '/' + str(page) + '/' + post
            page += 1

    def process(self, buff):
        soup = bs4.BeautifulSoup(buff)
        trs = soup.select('table > tr')[:-1]

        sources = []
        for tr in trs:
            details = tr.select('font.detDesc')[0].text

            (amount, suffix) = re.findall(r'([0-9\.]+)\s([GMK])iB', details, re.IGNORECASE)[0]
            size = int(float(amount) * self._SIZE_TABLE[suffix])

            sources.append({
                'name': tr.findAll('a')[2].text,
                'uri': tr.findAll('a')[3]['href'],
                'size': size,
                'timestamp': utcnow_timestamp(),
                'seeds': int(tr.findAll('td')[-2].text),
                'leechers': int(tr.findAll('td')[-1].text)
            })

        return sources


@app.register('importer', 'tpbrss')
class TpbRssImporter:
    BASE_URL = 'http://rss.thepiratebay.se/100'

    def url_generator(self, url=None):
        """Generates URLs for the current website,
        TPB doesn't support pagination on feeds
        """
        if url is None:
            url = self.BASE_URL

        yield url
        raise StopIteration()

    def process(self, buff):
        def _build_source(entry):
            return {
                'uri': entry['link'],
                'name': entry['title'],
                'timestamp': int(time.mktime(entry['published_parsed'])),
                'size': int(entry['contentlength'])
            }

        return list(map(_build_source, feedparser.parse(buff)['entries']))
