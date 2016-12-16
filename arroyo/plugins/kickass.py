# -*- coding: utf-8 -*-

from arroyo import plugin


import datetime
import re
import time
from urllib import parse


import bs4
import humanfriendly
from appkit import utils


class KickAss(plugin.Origin):
    __extension_name__ = 'kickass'

    PROVIDER = 'kickass'

    _BASE_URI = 'https://kickass.cd'
    DEFAULT_URI = _BASE_URI + '/new/'
    URI_PATTERNS = [
        r'^http(s)?://([^.]\.)?kickass.[^.]{2,3}/',
        r'^http(s)?://([^.]\.)?kat.[^.]{2,3}/',
    ]

    _TYPES = {
        'audio': 'other',
        'anime': None,
        'applications': 'application',
        'books': 'book',
        'games': 'game',
        'movies': 'movie',
        'music': 'music',
        'other': 'other',
        'porn': 'xxx',
        'tv': 'episode',
        'video': None,  # Try to auto detect
        'xxx': 'xxx'
    }

    def __init__(self, *args, **kwargs):
        super(KickAss, self).__init__(*args, **kwargs)
        self._logger = self.app.logger.getChild('kickass-importer')

    def paginate(self):
        parsed = parse.urlparse(self.uri)
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

    def get_query_uri(self, query):
        _category_table = {
            'episode': 'tv',
            'movie': 'movies'
        }

        kind = query.kind
        params = query.params

        q = query.base_string
        if kind in _category_table:
            q += ' category:' + _category_table[kind]

        q = parse.quote_plus(q)
        return ('{domain}/usearch/{q}/?'
                'field=time_add&sorder=desc').format(
                    domain=self._BASE_URI,
                    q=q)

    def parse(self, buff, parser):
        """
        Finds referentes to sources in buffer.
        Returns a list with source infos

        FIXME: If not results are found KAT show a more generic search with a
        warning:
            Your search «***» did not match any documents
        """

        buff = buff.decode('utf-8')

        rows = []
        idx = 0

        lowerbuff = buff.lower()
        while True:
            try:
                link = idx + lowerbuff[idx:].index('magnet:?')
            except ValueError:
                break

            try:
                pre = lowerbuff[:link].rindex('<tr')
            except ValueError:
                break

            try:
                post = link + lowerbuff[link:].index('</tr>') + 5
            except ValueError:
                pass

            idx = post
            rows.append(bs4.BeautifulSoup(buff[pre:post], parser))

        ret = map(self._process_row, rows)
        ret = filter(lambda x: x, ret)
        return list(ret)

    def _process_row(self, row):
        # Name
        names = row.select('a.cellMainLink')
        if len(names) != 1:
            return None
        name = names[0].text

        # Link
        magnets = set([x.attrs.get('href')
                       for x in row.select('a[href^=mag]')])
        if len(magnets) != 1:
            return None
        uri = list(magnets)[0]

        # Check for size
        try:
            size = row.select('td')[1].text.replace(' ', '')
            size = humanfriendly.parse_size(size)
        except (IndexError, humanfriendly.InvalidSize):
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

        return {
            'name': name,
            'uri': uri,
            'type': self._parse_type(row),
            'size': size,
            'seeds': seeds,
            'leechers': leechers,
            'created': self._parse_created(row.select('td')[2]),
        }

    def _parse_type(self, typ):
        m = re.search(r'posted by .+ in (.+)(\n+)?', typ.text.lower())

        if not m:
            msg = "Error parsing category: {category}"
            msg = msg.format(category=typ.text.replace('\n', ''))
            self._logger.error(msg)
            return None

        category = m.group(1).strip()
        idx = category.find(' > ')
        if idx >= 0:
            category = category[0:idx]
            # subcategory = category[idx+3:]

        try:
            return self._TYPES[category]
        except KeyError:
            msg = "Unknow category: {category}"
            msg = msg.format(category=category)
            self._logger.warning(msg)

    def _parse_created(self, created):
        _table = {
            'sec': 1,
            'min': 60,
            'hour': 60*60,
            'day': 60*60*24,
            'week': 60*60*24*7,
            'month': 60*60*24*30,
            'year': 60*60*24*365,
        }

        created = created.text.lower()

        # 23 weeks ago
        m = re.search(r'(?P<amount>\d+).+(?P<qual>sec|min|hour|day|week|month|year)',  # nopep8
                      created)
        if m:
            amount = int(m.group(1))
            qual = m.group(2)
            created = utils.now_timestamp() - (amount*_table[qual])
            return created

        # 02-22 12:30
        m = re.search(r'(\d{2})-(\d{2})\s+(\d+):(\d+)',
                      created)
        if m:
            today = datetime.date.today()
            created_str = '{}-{}-{} {}:{}:00'.format(
                today.year, m.group(1), m.group(2),
                m.group(3), m.group(4))

            today = datetime.date.today()
            x = humanfriendly.parse_date(created_str)
            x = datetime.datetime(*x).timetuple()
            x = time.mktime(x)
            created = int(x)
            return created

        # y-day 04:41
        m = re.search(r'y-day\s+(\d{2}):(\d{2})', created)
        if m:
            today = datetime.date.today()
            yday = today - datetime.timedelta(days=1)
            x = humanfriendly.parse_date('{}-{}-{} {}:{}:00'.format(
                yday.year, yday.month, yday.day,
                m.group(1), m.group(2)))
            x = datetime.datetime(*x).timetuple()
            x = time.mktime(x)
            created = int(x)
            return created

        # Today 13:30
        m = re.search(r'today\s+(\d{2}):(\d{2})', created)
        if m:
            today = datetime.date.today()
            x = humanfriendly.parse_date('{}-{}-{} {}:{}:00'.format(
                today.year, today.month, today.day,
                m.group(1), m.group(2)))
            x = datetime.datetime(*x).timetuple()
            x = time.mktime(x)
            created = int(x)
            return created

        # 08-31 2012
        m = re.search(r'(\d{2})-(\d{2})\s+(\d{4})', created)
        if m:
            today = datetime.date.today()
            x = humanfriendly.parse_date('{}-{}-{} 00:00:00'.format(
                m.group(3), m.group(1), m.group(2)))
            x = datetime.datetime(*x).timetuple()
            x = time.mktime(x)
            created = int(x)
            return created

        msg = "Invalid created format: {value}"
        msg = msg.format(value=created)
        self.app.logger.error(msg)

        return None

__arroyo_extensions__ = [
    KickAss
]
