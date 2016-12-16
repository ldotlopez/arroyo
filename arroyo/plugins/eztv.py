# -*- coding: utf-8 -*-

from arroyo import plugin


import re
from urllib import parse


import bs4
import humanfriendly
from appkit import utils


class Eztv(plugin.Origin):
    __extension_name__ = 'eztv'

    _BASE_DOMAIN = 'https://eztv.ag'

    DEFAULT_URI = _BASE_DOMAIN + '/page_0'
    PROVIDER = 'eztv'
    URI_PATTERNS = [
        r'^http(s)?://([^.]\.)?eztv\.[^.]{2,3}/'
    ]

    COUNT_NONE = 0
    COUNT_ONE = 1
    COUNT_MULTIPLE = 2

    def paginate(self):
        parsed = parse.urlparse(self.uri)
        pathcomponents = parsed.path.split('/')
        pathcomponents = list(filter(lambda x: x, pathcomponents))

        # https://eztv.ag/ -> 0 if not pathcomponents:
        if not pathcomponents:
            yield self.DEFAULT_URI
            return

        # https://eztv.ag/shows/546/black-mirror/
        if len(pathcomponents) != 1:
            yield self.uri
            return

        # Anything non standard
        m = re.findall(r'^page_(\d+)$', pathcomponents[0])
        if not m:
            yield self.uri
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
        kind = query.kind
        params = query.params

        if kind != 'episode':
            return

        series = params.get('series')
        if not series:
            return

        q = series.strip().replace(' ', '-')
        q = parse.quote_plus(q)

        return '{base}/search/{q}'.format(base=self._BASE_DOMAIN, q=q)

    def parse(self, buff, parser):
        """
        Finds referentes to sources in buffer.
        Returns a list with source infos
        """
        soup = bs4.BeautifulSoup(buff, parser)
        rows = soup.select('tr')
        rows = [x for x in rows
                if self.pseudocount_magnet_links(x) == self.COUNT_ONE]
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
            return cls.COUNT_NONE

        idx2 = node_str[idx1+1:].find('magnet:?')
        if idx2 == -1:
            return cls.COUNT_ONE

        return cls.COUNT_MULTIPLE

    @classmethod
    def find_convenient_parent(cls, node):
        """
        Find the parent (or grantparent, etc) of the node that has all the
        information needed.
        Currently this method searches for the most top node that has one (and
        only) magnet link
        """

        curr_count = cls.pseudocount_magnet_links(node)

        while True:
            parent = node.parent
            if parent is None:
                if curr_count == cls.COUNT_ONE:
                    return node
                else:
                    return None

            parent_count = cls.pseudocount_magnet_links(node.parent)
            if parent_count == cls.COUNT_MULTIPLE:
                return node

            curr_count = parent_count
            node = node.parent

    @classmethod
    def parse_name_and_uri(cls, node):
        magnet = node.select_one('a[href^=magnet:?]')
        parsed = parse.urlparse(magnet.attrs['href'])
        name = parse.parse_qs(parsed.query)['dn'][0]

        return (name, magnet.attrs['href'])

    @classmethod
    def parse_size(cls, node):
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

    @classmethod
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

    @classmethod
    def parse_row(cls, row):
        # Get magnet and name from the magnet link
        name, magnet = cls.parse_name_and_uri(row)
        try:
            size = cls.parse_size(row)
        except ValueError:
            size = None

        try:
            created = cls.parse_created(row)
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
