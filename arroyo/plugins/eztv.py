# -*- coding: utf-8 -*-

from arroyo import plugin


import re
from urllib import parse

import bs4
import humanfriendly
from ldotcommons import fetchers, utils


class Eztv(plugin.Origin):
    _BASE_DOMAIN = 'https://eztv.ag'

    DEFAULT_URI = _BASE_DOMAIN + '/page_0'
    PROVIDER = 'eztv'

    _table_mults = {
        's': 1,
        'm': 60,
        'h': 60*60,
        'd': 60*60*24,
        'w': 60*60*24*7,
        'mo': 60*60*24*30,
        'y': 60*60*24*365,
    }

    def paginate(self):
        parsed = parse.urlparse(self.uri)
        pathcomponents = parsed.path.split('/')
        pathcomponents = list(filter(lambda x: x, pathcomponents))

        # https://eztv.ag/ -> 0 if not pathcomponents:
        if not pathcomponents:
            yield self.DEFAULT_URI
            return

        # https://eztv.ag/shows/546/black-mirror/
        if len(pathcomponents) != 1:
            yield self.uri
            return

        # Anything non standard
        m = re.findall(r'^page_(\d+)$', pathcomponents[0])
        if not m:
            yield self.uri
            return

        # https://eztv.ag/page_0
        page = int(m[0])
        while True:
            yield '{scheme}://{netloc}/page_{page}'.format(
                scheme=parsed.scheme,
                netloc=parsed.netloc,
                page=page)
            page += 1

    def get_query_uri(self, query):
        kind = query.kind
        params = query.params

        if kind != 'episode':
            return

        series = params.get('series')
        if not series:
            return

        return '{base}/search/{q}'.format(
            base=self._BASE_DOMAIN, q=series.strip().replace(' ', '-')
        )

    def parse(self, buff):
        """
        Finds referentes to sources in buffer.
        Returns a list with source infos
        """

        def parse_row(row):
            children = row.findChildren('td')
            if len(row.findChildren('td')) != 6:
                return None

            try:
                ret = {
                    'name': children[1].text.strip(),
                    'uri': children[2].select('a.magnet')[0]['href'],
                    'language': 'eng-us',
                    'type': 'episode'
                }
            except (IndexError, AttributeError):
                return None

            try:
                ret['size'] = int(humanfriendly.parse_size(
                    children[3].text.strip()))
            except (IndexError, ValueError, humanfriendly.InvalidSize):
                pass

            created = children[4].text
            diff = 0

            m = re.search(r'(\d+)([mhd]) (\d+)([smhd])', created)
            if m:
                amount1 = int(m.group(1))
                qual1 = m.group(2)
                amount2 = int(m.group(3))
                qual2 = m.group(4)
                diff = (
                    amount1 * self._table_mults[qual1] +
                    amount2 * self._table_mults[qual2])

            else:
                m = re.search(r'(\d+) (w|mo|y)', created)
                if m:
                    diff = int(m.group(1)) * self._table_mults[m.group(2)]

            ret['created'] = utils.now_timestamp() - diff

            return ret

        soup = bs4.BeautifulSoup(buff, "html.parser")
        ret = map(parse_row, soup.select('tr'))
        ret = filter(lambda x: x is not None, ret)

        return ret


__arroyo_extensions__ = [
    ('eztv', Eztv)
]
