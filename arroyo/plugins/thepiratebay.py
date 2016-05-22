# -*- coding: utf-8 -*-

from arroyo import plugin


from datetime import datetime
import random
import re
import time


import bs4
import feedparser
import humanfriendly
from ldotcommons import utils


class _CategoryUnknowError(Exception):
    pass


class ThePirateBay(plugin.Origin):
    PROVIDER_NAME = 'thepiratebay'

    # TLD = random.sample(['am', 'gs', 'mn', 'la', 'vg'], 1)[0]
    _TLD = 'cr'
    BASE_URL = 'http://thepiratebay.{tld}/recent/0/'.format(tld=_TLD)

    _TYPE_TABLE = {
        'audio': {
            'music': 'music',
            'audio books': 'book',
            'sound clips': 'other',
            'flac': 'music',
            'other': 'other'
        },
        'video': {
            'movies': 'movie',
            'movies dvdr': 'movie',
            'music videos': 'other',
            'Movie clips': 'other',
            'tv shows': 'episode',
            'handheld': 'other',
            'hd - movies': 'movie',
            'hd - tv shows': 'episode',
            '3d': 'other',
            'other': 'other',
        },
        'applications': {
            'android': 'other',
            'handheld': 'other',
            'ios (ipad/iphone)': 'other',
            'mac': 'other',
            'other os': 'other',
            'unix': 'other',
            'windows': 'other'
        },
        'games': {
            'android': 'other',
            'handheld': 'other',
            'ios (ipad/iphone)': 'other',
            'mac': 'other',
            'other': 'other',
            'pc': 'other',
            'psx': 'other',
            'wii': 'other',
            'xbox360': 'other'
        },
        'porn': {
            'movies': 'xxx',
            'games': 'xxx',
            'hd - movies': 'xxx',
            'movie clips': 'xxx',
            'movies dvdr': 'xxx',
            'other': 'xxx',
            'pictures': 'xxx'
        },
        'other': {
            'e-books': 'book',
            'comics': 'other',
            'covers': 'other',
            'other': 'other',
            'physibles(?!)': 'other',
            'pictures': 'other'
        }
    }

    def paginate(self, url):
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

    def get_query_url(self, query):
        t = {
            'source': 'name',
            'episode': 'series',
            'movie': 'title'
        }
        selector = query.get('kind')
        field = t.get(selector, 'other')
        if not field:
            return

        q = 'other'
        for suffix in ['', '-glob', '-like', '-regexp']:
            q = query.get(field + suffix, 'other')
            if q is not 'other':
                q = q.replace('%', ' ').replace('*', ' ')
                q = q.strip()
                q = re.sub(r'[^a-zA-Z0-9]', ' ', q)
                break

        if q:
            return "https://thepiratebay.{tld}/search/{q}/0/99/0".format(
                   tld=self._TLD,
                   q=q)

    def parse(self, buff):
        def parse_row(row):
            details = row.select('font.detDesc')[0].text

            # Parse category
            try:
                typ = self.parse_category(row.select('td')[0].text)
            except _CategoryUnknowError as e:
                typ = 'other'
                msg = "Unknow category: '{category}'"
                msg = msg.format(category=e.args[0])
                self.app.logger.warning(msg)

            # Parse size
            size = re.findall(r'([0-9\.]+\s*[GMK]i?B)',
                              details,
                              re.IGNORECASE)[0]
            size = humanfriendly.parse_size(size)

            # Parse created
            try:
                created = self.parse_timestamp(row.select('.detDesc')[0].text)
            except IndexError:
                created = 'other'

            return {
                'name': row.findAll('a')[2].text,
                'uri': row.findAll('a')[3]['href'],
                'type': typ,
                'size': size,
                'created': created,  # utils.now_timestamp(),
                'seeds': int(row.findAll('td')[-2].text),
                'leechers': int(row.findAll('td')[-1].text)
            }

        def filter_row(row):
            return any((link.attrs.get('href', '').startswith('magnet')
                        for link in row.select('a')))

        soup = bs4.BeautifulSoup(buff, "html.parser")
        rows = soup.select('tr')
        rows = filter(filter_row, rows)
        return map(parse_row, rows)

    @classmethod
    def parse_category(cls, text):
        cat = text.lower()
        cat = cat.replace('(', '').replace(')', '')
        cat = cat.replace('\n', '\0').replace('\t', '\0').split('\0')
        cat = [x for x in cat if x]

        try:
            typ = cls._TYPE_TABLE[cat[0]][cat[1]]
        except KeyError:
            raise _CategoryUnknowError(cat[0] + '>' + cat[1])

        return typ

    @classmethod
    def parse_timestamp(cls, text):
        def conv(d):
            keys = now_dt.copy()
            keys.update({k: int(v) for (k, v) in d.items()})

            p = '{Y:04d} {m:02d} {d:02d} {H:02d} {M:02d} {S:02d}'
            p = p.format(**keys)
            p = datetime.strptime(p, '%Y %m %d %H %M %S')

            return int(time.mktime(p.timetuple()))

        now = utils.now_timestamp()
        now_dt = datetime.now()
        now_dt = dict(
            Y=now_dt.year,
            m=now_dt.month,
            d=now_dt.day,
            H=now_dt.hour,
            M=now_dt.minute,
            S=now_dt.second
        )

        text = text.lower().replace('&nbsp;', ' ')

        # 20 mins ago
        m = re.search(r'(\d+).+?mins', text)
        if m:
            return now - int(m.group(1)) * 60

        # today 13:14
        # yester 15:19
        m = re.search(r'(?P<mod>yester|today).+?(?P<H>\d+):(?P<M>\d+)',
                      text)
        if m:
            d = m.groupdict()
            mod = d.pop('mod')
            x = conv(d)
            return x if mod == 'today' else x - (60*60*24)

        # 07-15 13:34
        m = re.search(r'(?P<m>\d+)-(?P<d>\d+).+?(?P<H>\d+):(?P<M>\d+)',
                      text)
        if m:
            return conv(m.groupdict())

        # 07-15 2004
        m = re.search(r'(?P<m>\d+)-(?P<d>\d+).+?(?P<Y>\d{4})',
                      text)
        if m:
            return conv(m.groupdict())

        return now


class ThePirateBayRSS(plugin.Origin):

    PROVIDER_NAME = 'thepiratebayrss'
    BASE_URL = 'http://thepiratebay.{tld}/rss/'.format(
        tld=random.sample([
            'am', 'gs', 'mn', 'la', 'vg'
        ], 1)[0])

    def paginate(self, url):
        yield url

    # def url_generator(self, url='other'):
    #     """Generates URLs for the current website,
    #     TPB doesn't support pagination on feeds
    #     """
    #     if url is 'other':
    #         url = self.BASE_URL

    #     yield url
    #     raise StopIteration()

    def process_buffer(self, buff):
        def _build_source(entry):
            return {
                'uri': entry['link'],
                'name': entry['title'],
                'created': int(time.mktime(entry['published_parsed'])),
                'size': int(entry['contentlength'])
            }

        return map(_build_source, feedparser.parse(buff)['entries'])


__arroyo_extensions__ = [
    ('thepiratebay', ThePirateBay),
    ('thepiratebayrss', ThePirateBayRSS)
]
