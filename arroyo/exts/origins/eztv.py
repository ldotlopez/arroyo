# -*- coding: utf-8 -*-
# [SublimeLinter pep8-max-line-length:119]
# vim: set fileencoding=utf-8 :

import re
from urllib import parse

import bs4

from arroyo import exts


class Eztv(exts.Origin):
    BASE_URL = 'https://eztv.ch/page_0'
    PROVIDER_NAME = 'eztv'

    def paginate(self, url):
        parsed = parse.urlparse(url)
        pathcomponents = parsed.path.split('/')
        pathcomponents = list(filter(lambda x: x, pathcomponents))

        # https://eztv.ch/ -> 0
        if not pathcomponents:
            yield from self.paginate(url + '/page_0')
            return

        # https://eztv.ch/shows/546/black-mirror/
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
        selector = query.get('kind')
        if selector != 'episode':
            return

        series = query.get('series')
        if not series:
            return

        buff = self.app.fetcher.fetch('https://eztv.ch/showlist/')
        soup = bs4.BeautifulSoup(buff, "html.parser")

        series = series.lower()
        if series.startswith('the '):
            series = '{}, the'.format(series[4:])

        year = query.get('year')
        if year:
            series += ' ({})'.format(year)

        g = (x for x in soup.select('tr td a.thread_link') if x.text)
        g = filter(lambda x: x.text.lower() == series, g)

        try:
            return 'https://eztv.ch{}'.format(next(g).attrs['href'])
        except (StopIteration, KeyError):
            return None

    def process_buffer(self, buff):
        """
        Finds referentes to sources in buffer.
        Returns a list with source infos
        """

        def parse_row(row):
            children = row.findChildren('td')
            if len(row.findChildren('td')) != 5:
                return None

            try:
                return {
                    'name': children[1].text.strip(),
                    'uri': children[2].select('a.magnet')[0]['href'],
                    'language': 'eng-us',
                    'type': 'episode'
                }
            except (IndexError, AttributeError):
                return None

        soup = bs4.BeautifulSoup(buff, "html.parser")
        return map(parse_row, soup.select('tr'))

__arroyo_extensions__ = [
    ('origin', 'eztv', Eztv)
]
