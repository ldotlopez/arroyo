# -*- coding: utf-8 -*-
# [SublimeLinter pep8-max-line-length:119]
# vim: set fileencoding=utf-8 :

import re
from urllib import parse

import bs4
from ldotcommons import utils

from arroyo import exts


class Eztv(exts.Origin):
    BASE_URL = 'https://eztv.ch/page_0'

    def paginate(self, url):
        parsed = parse.urlparse(url)
        pathcomponents = parsed.path.split('/')
        pathcomponents = list(filter(lambda x: x, pathcomponents))

        # https://eztv.ch/ -> 0
        # https://eztv.ch/shows/546/black-mirror/ -> 3
        if len(pathcomponents) != 1:
            yield url
            return

        # Anything non standard
        m = re.findall(r'^page_(\d+)$', pathcomponents[0])
        if not m:
            yield url
            return

        # https://eztv.ch/page_0
        page = int(m[0])
        while True:
            yield '{scheme}://{netloc}/page_{page}'.format(
                scheme=parsed.scheme,
                netloc=parsed.netloc,
                page=page)
            page += 1

    def get_query_url(self, query):
        return

    def process_buffer(self, buff):
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
    ('origin', 'eztv', Eztv)
]
