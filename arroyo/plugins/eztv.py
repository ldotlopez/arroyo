# -*- coding: utf-8 -*-

from arroyo import plugin


import re
from urllib import parse

import bs4
import humanfriendly
from ldotcommons import fetchers, utils


class Eztv(plugin.Origin):
    BASE_DOMAIN = 'https://eztv.ag'
    BASE_URL = BASE_DOMAIN + '/page_0'
    PROVIDER_NAME = 'eztv'

    _table_mults = {
        's': 1,
        'm': 60,
        'h': 60*60,
        'd': 60*60*24,
        'w': 60*60*24*7,
        'mo': 60*60*24*30,
        'y': 60*60*24*365,
    }

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

        try:
            buff = self.app.get_fetcher().fetch(self.BASE_DOMAIN + '/showlist/')
        except fetchers.FetchError as e:
            msg = 'Unable to fetch {url}: {msg}'
            msg = msg.format(url=self.BASE_DOMAIN + '/showlist/', msg=str(e))
            self.logger.error(msg)
            return

        table = self.parse_series_index(buff)

        try:
            return self.get_url_for_series(table, series, query.get('year'))
        except KeyError:
            return None

    def get_url_for_series(self, table, series, year=None):
        table_lower = {k.lower(): v for (k, v) in table.items()}

        key = series.lower()
        if year:
            key += ' ({})'.format(year)

        try:
            return table_lower[key]
        except KeyError as e:
            pass

        raise KeyError(series)

    def parse_series_index(self, buff):
        def parse_row(x):
            name = x.text
            href = x.attrs.get('href', '')

            if not href.startswith('/shows/') or not name:
                return None

            if name.lower().endswith(', the'):
                name = 'The ' + name[:-5]

            return (name, self.BASE_DOMAIN + href)

        soup = bs4.BeautifulSoup(buff, "html.parser")
        shows = (parse_row(x) for x in soup.select('tr td a.thread_link'))
        shows = filter(lambda x: x, shows)

        return {x[0]: x[1] for x in shows}

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
