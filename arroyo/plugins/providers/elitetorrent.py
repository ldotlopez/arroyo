# -*- coding: utf-8 -*-


from arroyo import pluginlib


import asyncio
import collections
import functools
import re
import time
from datetime import datetime
from urllib import parse


import bs4
from appkit import utils


class EliteTorrent(pluginlib.Provider):
    __extension_name__ = 'elitetorrent'

    DEFAULT_URI = 'http://www.elitetorrent.net/descargas/'
    SEARCH_URI = ('http://www.elitetorrent.net/resultados/{query}'
                  '/orden:fecha')
    URI_PATTERNS = [
        r'^http(s)?://([^.]+\.)?elitetorrent.net/'
    ]

    type_map = {
        'series': 'episode',
        'series vose': 'episode',
        'peliculas': 'movie',
        'peliculas microhd': 'movie',
        'peliculas hdrip': 'movie',
        'estrenos': 'movie'
    }

    default_language = 'spa-es'
    _langs = [
        'spa-es',
        'lat-es'
    ]

    @staticmethod
    @functools.lru_cache(maxsize=8)
    def re_cache(re_str):
        return re.compile(re_str)

    def paginate(self, uri):
        if self.re_cache(r'/torrent/\d+/').search(uri):
            yield uri
            return

        parsed = parse.urlparse(uri)

        # elitetorrent passes thru extenal site to set cookies.
        # paginating that url leads to incorrect url and 404 errors.
        if not parsed.netloc.endswith('elitetorrent.net'):
            yield uri
            return

        # Split paths and params from parsed URI
        tmp = [x for x in parsed.path.split('/') if x]
        paths = []
        params = collections.OrderedDict({
            'orden': 'fecha',
            'pag': 1
        })

        for c in tmp:
            if ':' in c:
                k, v = c.split(':', 1)
                params[k] = v
            else:
                paths.append(c)

        pag_n = params.pop('pag')
        try:
            pag_n = int(pag_n)
        except ValueError:
            pag_n = 1

        while True:
            params['pag'] = pag_n
            pag_n += 1

            parsed = parsed._replace(
                path='/'.join(
                    paths +
                    ['{}:{}'.format(k, v) for (k, v) in params.items()]
                )
            )

            yield parse.urlunparse(parsed)

    def get_query_uri(self, query):
        if query.params.get('language', None) not in self._langs:
            return

        q = query.base_string

        if not q:
            return None

        if query.kind == 'episode':
            q = re.sub(r' S0*(\d+)$',
                       lambda m: ' Temporada ' + m.group(1),
                       query.base_string)
            q = re.sub(r' S0*(\d+)E(\d+)$',
                       lambda m: ' ' + m.group(1) + 'x' + m.group(2),
                       query.base_string)

        # elitetorrent only allows searches with 6 words
        words = [x for x in q.split(' ') if x]
        if len(words) > 6:
            diff = (len(words) - 6) // 2
            words = words[diff:diff+6]
        q = ' '.join(words)

        q = parse.quote_plus(q)

        return self.SEARCH_URI.format(query=q)

    @asyncio.coroutine
    def fetch(self, fetcher, uri):
        def _is_redirect(content):
            soup = bs4.BeautifulSoup(
                content,
                self.app.settings.get('importer.parser'))

            for meta in soup.select('meta'):
                attrs = {k.lower(): v.lower() for (k, v) in meta.attrs.items()}
                if attrs.get('http-equiv') == 'refresh':
                    dummy, location = attrs.get('content').split(';', 1)
                    loctype, url = location.split('=', 1)
                    if loctype.lower() == 'url':
                        return True

            return False

        resp, content = yield from fetcher.fetch_full(uri)

        if _is_redirect(content):
            # Get Cookies
            resp, content = yield from fetcher.fetch_full(
                url, skip_cache=True)
            # Get URL with cookies
            resp, content = yield from fetcher.fetch_full(
                url, skip_cache=True)

        return content

    def parse(self, buff, parser):
        soup = bs4.BeautifulSoup(buff, parser)
        info = soup.select_one('.info-tecnica')
        if info:
            return self.parse_detailed(soup)
        else:
            return self.parse_listing(soup)

    def parse_listing(self, soup):
        torrent_href_re = re.compile(r'(https?://(www.)?elitetorrent.net)?/torrent/\d+/')  # nopep8

        def parse_link(x):
            href = x.attrs.get('href', '')
            text = x.text

            if text == '' or href == '':
                return None

            if not torrent_href_re.search(href):
                return None

            parent = x
            while parent != soup and parent.name.lower() not in ('tr', 'li'):
                parent = parent.parent

            if parent == soup:
                return None

            if href[0] == '/':
                href = 'http://www.elitetorrent.net' + href

            return dict(node=parent, name=text, uri=href)

        # Filter and torrent links that point to this site.
        links = [parse_link(x) for x in soup.select('a')]
        cards = [x for x in links if x]

        ret = []
        for x in cards:
            typ, language = self.parse_type_and_language(
                x['node'].select_one('.categoria')
            )
            created = self.parse_uploaded(x['node'].select_one('.fecha'))

            ret.append(dict(
                name=x['name'],
                uri=x['uri'],
                type=typ,
                language=language,
                created=created
            ))

        return ret

    def parse_detailed(self, soup):
        card = soup  # .select_one('#principal')

        name = card.select_one('h2').text
        uri = soup.select_one('a[href^=magnet:?]').attrs['href']
        typ, language = self.parse_type_and_language(
            card.select_one('.info-tecnica').select('dd')[1]
        )
        created = self.parse_uploaded(
            card.select_one('.info-tecnica').select('dd')[0]
        )

        name = soup.select_one('#box-ficha h2').text

        seeds, leechers = self.parse_seeds_and_leechers(
            card.select_one('#torrent-info')
        )

        return [dict(
            name=name,
            uri=uri,
            created=created,
            type=typ,
            language=language,
            seeds=seeds,
            leechers=leechers
        )]

    def parse_type_and_language(self, node):

        if node is None:
            return None

        text = node.text.lower()

        return (
            self.type_map.get(text, None),
            self.default_language if '(vose)' not in text else None
        )

    def parse_uploaded(self, node):
        ago_table = dict(
            seg=1,
            mi=60,
            h=60*60,
            d=60*60*24,
            sem=60*60*24*7,
            me=60*60*24*30,
            a=60*60*24*365
        )

        if node is None:
            return None

        text = node.text

        # In listings, dates are specified as "Hace 3 semanas"
        # (3 weeks ago)

        ago_re = r'Hace (un|\d+) (seg|mi|h|d|sem|me|a)'
        m = re.search(ago_re, text, re.IGNORECASE)
        if m:
            if m.group(2) not in ago_table:
                return None

            amount = 0
            if m.group(1) == 'un':
                amount = 1
            else:
                amount = int(m.group(1))

            return utils.now_timestamp() - amount * ago_table[m.group(2)]

        # In detail mode dates are more readable

        dmy_re = r'(\d+-\d+-\d+)'
        m = re.search(dmy_re, text, re.IGNORECASE)
        if m:
            tmp = datetime.strptime(m.group(1), '%d-%m-%Y')
            return int(time.mktime(tmp.timetuple()))

        # There are other formats like 'Hoy, 20:32'. It's simplier to just drop
        # it and go to defaults

        return None

    def parse_seeds_and_leechers(self, node):
        if node is None:
            return None

        text = node.text.lower()

        seeds_re = r'semillas\W+(\d+)'
        leechers_re = r'clientes\W+(\d+)'

        seeds_m = re.search(seeds_re, text)
        leechers_m = re.search(leechers_re, text)

        return (
            int(seeds_m.group(1)) if seeds_m else None,
            int(leechers_m.group(1)) if leechers_m else None,
        )


__arroyo_extensions__ = [
    EliteTorrent
]
