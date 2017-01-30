# -*- coding: utf-8 -*-


from arroyo import pluginlib


import bs4
from urllib import parse


class Epublibre(pluginlib.Provider):
    __extension_name__ = 'epublibre'

    DEFAULT_URI = 'https://epublibre.org/catalogo/index/0/nuevo/novedades/sin/todos'  # nopep8
    URI_PATTERNS = [
        r'^http(s)?://([^.]\.)?epublibre\.org/'
    ]

    def get_query_uri(self, query):
        q = query.base_string
        if not q:
            return

        return 'https://www.epublibre.org/catalogo/index/0/nuevo/todos/sin/todos/{q}'.format(  # nopep8
            q=parse.quote(q))

    def parse(self, buff, parser):
        soup = bs4.BeautifulSoup(buff, parser)

        if soup.select('#titulo_libro'):
            return self.parse_detailed(soup)
        else:
            return self.parse_listing(soup)

    def parse_listing(self, soup):
        def _parse_book(book):
            href = book.attrs['href']
            title = book.select_one('h1').text
            author = book.select_one('h2').text
            return {
                'name': '{author} {title}'.format(author=author, title=title),
                'meta': {
                    'book.author': author,
                    'book.title': title
                    },
                'type': 'book',
                'uri': href
             }

        ret = [_parse_book(x) for x in soup.select('a.popover-libro')]
        return ret

    def parse_detailed(self, soup):
        href = soup.select('a[href^=magnet:?]')
        title = soup.select_one('.det_titulo').text.strip()
        author = soup.select_one('.aut_sec').text.strip()
        return [{
            'urn': href,
            'name': '{author} {title}'.format(author=author, title=title)
        }]

__arroyo_extensions__ = [
    Epublibre
]
