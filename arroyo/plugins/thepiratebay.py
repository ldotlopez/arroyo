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


class Tpb(plugin.Origin):
    PROVIDER_NAME = 'thepiratebay'

    # TLD = random.sample(['am', 'gs', 'mn', 'la', 'vg'], 1)[0]
    TLD = 'cr'
    BASE_URL = 'http://thepiratebay.{tld}/recent/0/'.format(tld=TLD)

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
        field = t.get(selector, None)
        if not field:
            return

        q = None
        for suffix in ['', '-glob', '-like', '-regexp']:
            q = query.get(field + suffix, None)
            if q is not None:
                q = q.replace('%', ' ').replace('*', ' ')
                q = q.strip()
                q = re.sub(r'[^a-zA-Z0-9]', ' ', q)
                break

        if q:
            return "https://thepiratebay.{tld}/search/{q}/0/99/0".format(
                   tld=self.TLD,
                   q=q)

    def parse(self, buff):
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

        def parse_ts(text):
            def conv(d):
                keys = now_dt.copy()
                keys.update({k: int(v) for (k, v) in d.items()})

                p = '{Y:04d} {m:02d} {d:02d} {H:02d} {M:02d} {S:02d}'
                p = p.format(**keys)
                p = datetime.strptime(p, '%Y %m %d %H %M %S')

                return int(time.mktime(p.timetuple()))

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

        def parse_row(row):
            details = row.select('font.detDesc')[0].text

            size = re.findall(r'([0-9\.]+\s*[GMK]i?B)',
                              details,
                              re.IGNORECASE)[0]
            size = humanfriendly.parse_size(size)

            try:
                desc = row.select('.detDesc')[0].text
                desc = desc.lower().replace('&nbsp;', ' ')
                created = parse_ts(desc)
            except IndexError:
                created = None

            return {
                'name': row.findAll('a')[2].text,
                'uri': row.findAll('a')[3]['href'],
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


class TpbRss(plugin.Origin):

    PROVIDER_NAME = 'thepiratebayrss'
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
                'created': int(time.mktime(entry['published_parsed'])),
                'size': int(entry['contentlength'])
            }

        return map(_build_source, feedparser.parse(buff)['entries'])


__arroyo_extensions__ = [
    ('thepiratebay', Tpb),
    ('thepiratebayrss', TpbRss)
]
