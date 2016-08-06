# -*- coding: utf-8 -*-

from arroyo import plugin


import re
from urllib import parse


import bs4
import humanfriendly
from ldotcommons import utils


class KickAss(plugin.Origin):
    PROVIDER_NAME = 'kickass'
    BASE_DOMAIN = 'https://kickass.cd'
    BASE_URL = BASE_DOMAIN + '/new/'

    _TYPES = {
        'anime': 'other',
        'applications': 'application',
        'books': 'book',
        'games': 'game',
        'movies': 'movie',
        'music': 'music',
        'other': 'other',
        'tv': 'episode',
        'video': 'other',
        'xxx': 'xxx'  # ¯\_(ツ)_/¯
    }

    def __init__(self, *args, **kwargs):
        super(KickAss, self).__init__(*args, **kwargs)
        self._logger = self.app.logger.getChild('kickass-importer')

    def paginate(self, url):
        parsed = parse.urlparse(url)
        paths = [x for x in parsed.path.split('/') if x]

        try:
            page = int(paths[-1])
            paths = paths[:-1]
        except (IndexError, ValueError):
            page = 1

        while True:
            if page > 1:
                tmp = paths + [str(page)]
            else:
                tmp = paths

            yield parse.urlunparse(parsed._replace(path='/'.join(tmp) + '/'))
            page += 1

    def get_query_url(self, query):
        selector = query.get('kind')

        if selector == 'episode':
            series = query.get('series')
            if not series:
                return

            q = '{} category:tv'.format(series)

            season = query.get('season')
            if season:
                q += ' season:{}'.format(season)

            episode = query.get('episode')
            if episode:
                q += ' episode:{}'.format(episode)

        elif selector == 'movie':
            title = query.get('title', '')
            if not title:
                return

            q = '{} category:movies'.format(title)

        else:
            q = query.get('name') or \
                query.get('name-glob') or \
                query.get('name-like') or \
                query.get('name-regexp') or ''
            q = q.replace('%', ' ').replace('*', ' ')
            q = q.strip()

        if not q:
            return

        return ('{domain}/usearch/{q}/?'
                'field=time_add&sorder=desc').format(
                    domain=self.BASE_DOMAIN,
                    q=parse.quote(q))

    def parse(self, buff):
        """
        Finds referentes to sources in buffer.
        Returns a list with source infos

        FIXME: If not results are found KAT show a more generic search with a
        warning:
            Your search «***» did not match any documents
        """

        def process_row(row):
            row_as_text = row.text

            # Check for name
            try:
                name = row.select('a.cellMainLink')[0].text
            except IndexError:
                name = None

            try:
                hrefs = (x.attrs.get('href') for x in row.select('a'))
                magnets = filter(lambda x: x.startswith('magnet:?'), hrefs)
                uri = list(magnets)[0]
            except (IndexError, AttributeError):
                uri = None

            # Check for size
            try:
                size = row.select('td')[1].text.replace(' ', '')
                size = humanfriendly.parse_size(size)
            except (IndexError, ValueError):
                size = None

            # Check for seeds
            try:
                seeds = int(row.select('td')[-2].text)
            except (IndexError, ValueError):
                seeds = None

            # Check for leechers
            try:
                leechers = int(row.select('td')[-1].text)
            except (IndexError, ValueError):
                leechers = None

            # Check for type
            typ = None

            m = re.search('Posted by .+ in (.+)', row_as_text)
            if m:
                category = m.group(1).strip().lower()
                idx = category.find(' > ')
                if idx >= 0:
                    category = category[0:idx]
                    # subcategory = category[idx+3:]

                try:
                    typ = self._TYPES[category]
                except IndexError:
                    typ = None
                    msg = "Unknow category: {category}"
                    msg = msg.format(category=category)
                    self._logger.warning(msg)

            try:
                _table = {
                    'sec': 1,
                    'min': 60,
                    'hour': 60*60,
                    'day': 60*60*24,
                    'week': 60*60*24*7,
                    'month': 60*60*24*30,
                    'year': 60*60*24*365,
                }
                created = row.select('td')[3].text
                m = re.search(r'(\d+).+(sec|min|hour|day|week|month|year)',
                              row.select('td')[3].text)
                amount = int(m.group(1))
                qual = m.group(2)
                created = utils.now_timestamp() - (amount*_table[qual])
            except IndexError:
                created = None

            return {
                'name': name,
                'uri': uri,
                'type': typ,
                'size': size,
                'seeds': seeds,
                'leechers': leechers,
                'created': created,
            }

        soup = bs4.BeautifulSoup(buff, "html.parser")
        return map(process_row, soup.select('table.data tr')[1:])


__arroyo_extensions__ = [
    ('kickass', KickAss)
]
