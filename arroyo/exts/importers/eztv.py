# -*- coding: utf-8 -*-
# [SublimeLinter pep8-max-line-length:119]
# vim: set fileencoding=utf-8 :

import re
from urllib import parse

import bs4
from ldotcommons import utils

from arroyo import exts


class EztvImporter(exts.Importer):
    BASE_URL = 'http://eztv.it/page_0'

    def url_generator(self, url=None):
        if not url:
            url = self.BASE_URL

        p = parse.urlparse(url)
        if p.path.startswith('/shows/'):
            yield url
            raise StopIteration()

        m = re.match('/page_(\d+)', p.path)
        if not m:
            idx = 0
        else:
            idx = int(m.group(1))

        while True:
            yield 'http://eztv.it/page_{}'.format(idx)
            idx += 1

    def process(self, buff):
        """
        Finds referentes to sources in buffer.
        Returns a list with source infos
        """
        soup = bs4.BeautifulSoup(buff)

        sources = []
        for tr in soup.select('tr'):
            children = tr.findChildren('td')
            if len(children) != 5:
                continue

            try:
                sources.append({
                    'name': children[1].text.strip(),
                    'uri': children[2].select('a.magnet')[0]['href'],
                    'timestamp': utils.utcnow_timestamp(),
                    'type': 'episode',
                    'language': 'eng-US'
                })
            except IndexError:
                continue

        return sources

__arroyo_extensions__ = [
    ('importer', 'eztv', EztvImporter)
]
