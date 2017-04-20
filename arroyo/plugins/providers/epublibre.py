# -*- coding: utf-8 -*-

# Copyright (C) 2015 Luis López <luis@cuarentaydos.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301,
# USA.


from arroyo import pluginlib


from urllib import parse


class Epublibre(pluginlib.Provider):
    __extension_name__ = 'epublibre'

    DEFAULT_URI = 'https://epublibre.org/catalogo/index/0/nuevo/novedades/sin/todos'  # nopep8
    URI_PATTERNS = [
        r'^http(s)?://([^.]\.)?epublibre\.org/'
    ]

    def get_query_uri(self, query):
        if query['type'] != 'ebook':
            return

        q = query.base_string
        if not q:
            return

        return 'https://www.epublibre.org/catalogo/index/0/nuevo/todos/sin/todos/{q}'.format(  # nopep8
            q=parse.quote(q))

    def parse(self, buff):
        soup = self.parse_buffer(buff)

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
        href = soup.select_one('a[href^=magnet:?]').attrs['href']
        title = soup.select_one('.det_titulo').text.strip()
        author = soup.select_one('.aut_sec').text.strip()
        return [{
            'uri': href,
            'name': '{author} {title}'.format(author=author, title=title)
        }]

__arroyo_extensions__ = [
    Epublibre
]
