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

import enum
import re
from urllib import parse


import humanfriendly
from appkit import utils


class Eztv(pluginlib.Provider):
    __extension_name__ = 'eztv'

    _BASE_DOMAIN = 'https://eztv.ag'
    DEFAULT_URI = _BASE_DOMAIN + '/page_0'
    URI_PATTERNS = [
        r'^http(s)?://([^.]\.)?eztv\.[^.]{2,3}/'
    ]

    class Count(enum.Enum):
        NONE = 0
        ONE = 1
        MULTIPLE = 2

    def paginate(self, uri):
        parsed = parse.urlparse(uri)
        pathcomponents = parsed.path.split('/')
        pathcomponents = list(filter(lambda x: x, pathcomponents))

        # https://eztv.ag/ -> page_0 if not pathcomponents:
        if not pathcomponents:
            pathcomponents = ['page_0']

        # https://eztv.ag/shows/546/black-mirror/
        if len(pathcomponents) != 1:
            yield uri
            return

        # Anything non standard
        m = re.findall(r'^page_(\d+)$', pathcomponents[0])
        if not m:
            yield uri
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
        # eztv only has series
        if query.get('type', None) != 'episode':
            return

        try:
            series = query['series']
        except KeyError:
            return

        q = series.strip().replace(' ', '-')

        return '{base}/search/{q}'.format(
            base=self._BASE_DOMAIN,
            q=parse.quote_plus(q))

    def parse(self, buff):
        """
        Finds referentes to sources in buffer.
        Returns a list with source infos
        """
        soup = self.parse_buffer(buff)
        rows = soup.select('tr')
        rows = [x for x in rows
                if self.pseudocount_magnet_links(x) == Eztv.Count.ONE]
        # magnet_links = soup.select('a[href^=magnet:?]')
        # rows = [self.find_convenient_parent(x) for x in magnet_links]
        ret = [self.parse_row(x) for x in rows]

        return ret

    @classmethod
    def pseudocount_magnet_links(cls, node):
        """Count if node has 0, 1 or more magnet links"""

        node_str = str(node)
        idx1 = node_str.find('magnet:?')
        if idx1 == -1:
            return Eztv.Count.NONE

        idx2 = node_str[idx1+1:].find('magnet:?')
        if idx2 == -1:
            return Eztv.Count.ONE

        return Eztv.Count.MULTIPLE

    def find_convenient_parent(self, node):
        """
        Find the parent (or grantparent, etc) of the node that has all the
        information needed.
        Currently this method searches for the most top node that has one (and
        only) magnet link
        """

        curr_count = self.pseudocount_magnet_links(node)

        while True:
            parent = node.parent
            if parent is None:
                if curr_count == self.COUNT_ONE:
                    return node
                else:
                    return None

            parent_count = self.pseudocount_magnet_links(node.parent)
            if parent_count == self.COUNT_MULTIPLE:
                return node

            curr_count = parent_count
            node = node.parent

    def parse_name_and_uri(self, node):
        magnet = node.select_one('a[href^=magnet:?]')
        parsed = parse.urlparse(magnet.attrs['href'])
        name = parse.parse_qs(parsed.query)['dn'][0]

        return (name, magnet.attrs['href'])

    def parse_size(self, node):
        s = str(node)

        m = re.search(
            r'(\d+(\.\d+)?\s+[TGMK]B)',
            s,
            re.IGNORECASE)
        if not m:
            raise ValueError('No size value found')

        try:
            return humanfriendly.parse_size(m.group(0))
        except humanfriendly.InvalidSize as e:
            raise ValueError('Invalid size') from e

    def parse_created(cls, node):
        _table_mults = {
            's': 1,
            'm': 60,
            'h': 60*60,
            'd': 60*60*24,
            'w': 60*60*24*7,
            'mo': 60*60*24*30,
            'y': 60*60*24*365,
        }

        s = str(node)

        def _do_diff(diff):
            return utils.now_timestamp() - diff

        m = re.search(r'(\d+)([mhd]) (\d+)([smhd])', s)
        if m:
            amount1 = int(m.group(1))
            qual1 = m.group(2)
            amount2 = int(m.group(3))
            qual2 = m.group(4)
            diff = (
                amount1 * _table_mults[qual1] +
                amount2 * _table_mults[qual2])

            return _do_diff(diff)

        m = re.search(r'(\d+) (w|mo|y)', s)
        if m:
            diff = int(m.group(1)) * _table_mults[m.group(2)]
            return _do_diff(diff)

        raise ValueError('No created value found')

    def parse_row(self, row):
        # Get magnet and name from the magnet link
        name, magnet = self.parse_name_and_uri(row)
        try:
            size = self.parse_size(row)
        except ValueError:
            size = None

        try:
            created = self.parse_created(row)
        except ValueError:
            created = None

        return {
            'name': name,
            'uri': magnet,
            'size': size,
            'created': created,
            'language': 'eng-us',
            'type': 'episode'
        }


__arroyo_extensions__ = [
    Eztv
]
