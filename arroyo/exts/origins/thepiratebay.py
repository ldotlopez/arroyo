# -*- coding: utf-8 -*-
# [SublimeLinter pep8-max-line-length:119]
# vim: set fileencoding=utf-8 :

import random
import re
import time

import bs4
import feedparser
from ldotcommons.utils import utcnow_timestamp

from arroyo import exts


class Tpb(exts.Origin):
    PROVIDER_NAME = 'tpb'
    BASE_URL = 'http://thepiratebay.{tld}/recent/0/'.format(
        tld=random.sample([
            'am', 'gs', 'mn', 'la', 'vg'
        ], 1)[0])
    _SIZE_TABLE = {'K': 10 ** 3, 'M': 10 ** 6, 'G': 10 ** 9}

    def paginate(self, url):
        yield url

    # def url_generator(self, url=None):
    #     if url is None:
    #         url = self.BASE_URL

    #     # And '/' at the end
    #     if not url.endswith('/'):
    #         url += '/'

    #     # Get page
    #     try:
    #         page = int(re.findall(r'/(\d+)/', url)[0])
    #     except IndexError:
    #         page = 0
    #         url += '0/'

    #     pre, post = re.split(r'/\d+/', url, maxsplit=1)

    #     while True:
    #         yield pre + '/' + str(page) + '/' + post
    #         page += 1

    def process_buffer(self, buff):
        def parse_row(row):
            details = row.select('font.detDesc')[0].text

            (amount, suffix) = re.findall(r'([0-9\.]+)\s([GMK])iB',
                                          details,
                                          re.IGNORECASE)[0]
            size = int(float(amount) * self._SIZE_TABLE[suffix])

            return {
                'name': row.findAll('a')[2].text,
                'uri': row.findAll('a')[3]['href'],
                'size': size,
                'timestamp': utcnow_timestamp(),
                'seeds': int(row.findAll('td')[-2].text),
                'leechers': int(row.findAll('td')[-1].text)
            }

        soup = bs4.BeautifulSoup(buff)
        rows = soup.select('table tr')[1:-1]

        return map(parse_row, rows)


class TpbRss(exts.Origin):

    PROVIDER_NAME = 'tpbrss'
    BASE_URL = 'http://thepiratebay.{tld}/rss/'.format(
        tld=random.sample([
            'am', 'gs', 'mn', 'la', 'vg'
        ], 1)[0])

    def paginate(self, url):
        yield url

    # def url_generator(self, url=None):
    #     """Generates URLs for the current website,
    #     TPB doesn't support pagination on feeds
    #     """
    #     if url is None:
    #         url = self.BASE_URL

    #     yield url
    #     raise StopIteration()

    def process_buffer(self, buff):
        def _build_source(entry):
            return {
                'uri': entry['link'],
                'name': entry['title'],
                'timestamp': int(time.mktime(entry['published_parsed'])),
                'size': int(entry['contentlength'])
            }

        return map(_build_source, feedparser.parse(buff)['entries'])

__arroyo_extensions__ = [
    ('origin', 'tpb', Tpb),
    ('origin', 'tpbrss', TpbRss)
]
