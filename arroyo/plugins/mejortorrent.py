import re
import asyncio
from urllib import parse
from arroyo import plugin
from arroyo.plugin.tools import downloads
import bs4


class Origin(plugin.Origin):
    BASE_URL = "http://www.mejortorrent.com/secciones.php?sec=ultimos_torrents"
    PROVIDER_NAME = 'mejortorrent'
    _MAX_DEPTH = 5

    def __init__(self, *args, **kwargs):
        super(Origin, self).__init__(*args, **kwargs)
        self._seen = set()
        self._depth = 0

    def _extract_links(self, buff):
        soup = bs4.BeautifulSoup(buff, "html.parser")

        # Extract all links not seen
        links = soup.select('a')
        links = [x.attrs.get('href') for x in links]
        links = [x for x in links if x and x not in self._seen]

    @asyncio.coroutine
    def process(self, url, parser_func):
        try:
            buff = yield from self.fetch(url)

        except asyncio.CancelledError as e:
            msg = "Fetch cancelled '{url}' (possibly timeout)"
            msg = msg.format(url=url)
            self.app.logger.error(msg)
            return []

        except aiohttp.errors.ClientOSError as e:
            msg = "Client error fetching {url}: {e}"
            msg = msg.format(url=url, e=e)
            self.app.logger.error(msg)
            return []

        return parser_func(buff)

    def parse_table_page(self, buff):
        """
        Only direct links to torrent files are allowed
        """
        links = self._extract_links(buff)

        torrents = ['http://www.mejortorrent.com' + x for x in links
                    if x.endswith('.torrent')]

        self.push_to_sched(

    def parse_torrent_data(self, buff):
        magnet = downloads.magnet_from_torrent_data(buff)
        parsed = parse.urlparse(magnet)
        qs = parse.parse_qs(parsed.query)

        try:
            name = qs.get('dn')[-1]
        except (IndexError, TypeError):
            return []

        return [{
            'uri': magnet,
            'name': name
            }]

    def parse(self, buff, url, **kwargs):
        if self._depth > self._MAX_DEPTH:
            msg = "Max depth reached. Aborting"
            self.app.logger.warning(msg)
            return []

        if url.endswith('.torrent'):
            magnet = downloads.magnet_from_torrent_data(buff)
            parsed = parse.urlparse(magnet)
            qs = parse.parse_qs(parsed.query)

            try:
                name = qs.get('dn')[-1]
            except (IndexError, TypeError):
                return []

            return [{
                'uri': magnet,
                'name': name
                }]

        else:
            soup = bs4.BeautifulSoup(buff, "html.parser")

            # Extract all links not seen
            links = soup.select('a')
            links = [x.attrs.get('href') for x in links]
            links = [x for x in links if x and x not in self._seen]

            # Check for followups
            followups = ['http://www.mejortorrent.com' + x for x in links
                         if re.search('-descargar-torrents?.+-\d+.+\.html$', x)]
            followups += ['http://www.mejortorrent.com/' + x for x in links
                          if 'secciones.php?' in x and 'sec=descargas' in x]

            # Check for torrents
            torrents = ['http://www.mejortorrent.com' + x for x in links
                        if x.endswith('.torrent')]

            for x in followups + torrents:
                self._seen.add(x)
                self.push_to_sched(self.process(x))
            self._depth += 1

            return []

        # torrents = [self.BASE_URL + x for x in links
        #             if x and x.endswith('.torrent') and
        #             x not in seen]

        # followups = [self.BASE_URL + x for x in links
        #              if x and x not in torrents and x not in seen and (
        #                  '-descargar-' in x or
        #                  'link_bajar=1' in x)]

        # ret = []

        # for url in torrents:
        #     buff = self.app.fetcher.fetch(url)
        #     seen.add(url)
        #     ret.append(downloads.magnet_from_torrent_data(buff))

        # for url in followups:
        #     buff = self.app.fetcher.fetch(url)
        #     seen.add(url)
        #     ret.extend(self.process_buffer(buff, depth=depth+1, seen=seen))


__arroyo_extensions__ = [
    ('mejortorrent', Origin),
]
