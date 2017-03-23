# -*- coding: utf-8 -*-

from arroyo import pluginlib


import datetime
import re
import time
from urllib import parse


import humanfriendly
from appkit import (
    logging,
    utils
)


class KickAss(pluginlib.Provider):
    __extension_name__ = 'kickass'

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
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger('kickass')

    def paginate(self, uri):
        parsed = parse.urlparse(uri)
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
        category_table = {
            'episode': 'tv',
            'movie': 'movies'
        }

        q = query.base_string
        if not q:
            return

        if query.kind in category_table:
            q += ' category:' + category_table[query.kind]

        q = parse.quote_plus(q)
        return ('{domain}/usearch/{q}/?'
                'field=time_add&sorder=desc').format(
                    domain=self._BASE_URI,
                    q=q)

    def parse(self, buff):
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
            rows.append(self.parse_buffer(buff[pre:post]))

        ret = [self._process_row(x) for x in rows]
        ret = [x for x in ret if x]

        return ret

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

        try:
            typ = self._parse_type(row)
        except ValueError as e:
            msg = "Unknow category: {category}"
            msg = msg.format(category=e.args[0])
            self.logger.warning(msg)
            typ = None

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

        try:
            raw_created = row.select('td')[2]
            created = self._parse_created(raw_created)
        except ValueError as e:
            msg = "Invalid created format: {value}"
            msg = msg.format(value=raw_created)
            self.logger.error(msg)
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

    def _parse_type(self, typ):
        m = re.search(r'posted by .+ in (.+)(\n+)?', typ.text.lower())

        if not m:
            raise ValueError(typ.text.replace('\n', ''))

        category = m.group(1).strip()
        idx = category.find(' > ')
        if idx >= 0:
            category = category[0:idx]
            # subcategory = category[idx+3:]

        try:
            return self._TYPES[category]
        except KeyError as e:
            raise ValueError(category) from e

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

        raise ValueError(created)


__arroyo_extensions__ = [
    KickAss
]
