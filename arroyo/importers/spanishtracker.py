# -*- coding: utf-8 -*-
# vim: set fileencoding=utf-8 :

import re
import time
from urllib import parse

import bs4

from ldotcommons import logging
from arroyo import importers

NAME = "Spanish tracker"
BASE_URL = 'http://spanishtracker.com/torrents.php?page=0'

_SIZE_TABLE = {'K': 10 ** 3, 'M': 10 ** 6, 'G': 10 ** 9}
_MAGNET_STR = \
    r'magnet:?xt=urn:btih:{0[hash_string]}&dn={0[name]}&' + \
    r'tr=http%3A%2F%2Fwww.spanishtracker.com%3A2710%2Fannounce&' + \
    r'tr=http%3A%2F%2Ftracker.openbittorrent.com%3A80%2Fannounce&' + \
    r'tr=http%3A%2F%2Ftracker.publicbt.com%3A80%2Fannounce&' + \
    r'tr=http%3A%2F%2Ftpb.tracker.prq.to%3A80%2Fannounce&' + \
    r'tr=http%3A%2F%2Ftracker.prq.to%3A80%2Fannounce&' + \
    r'tr=udp%3A%2F%2Ftracker.openbittorrent.com%3A80&' + \
    r'tr=udp%3A%2F%2Ftracker.publicbt.com%3A80&' + \
    r'tr=udp%3A%2F%2Ftracker.openbittorrent.com%3A80&' + \
    r'tr=udp%3A%2F%2Ftracker.ccc.de%3A80&' + \
    r'tr=udp%3A%2F%2Ftracker.istole.it%3A6969'


_logger = logging.get_logger('spanishtracker')


def url_generator(url=None):
    if url is None:
        url = BASE_URL

    query = parse.parse_qs(parse.urlparse(url).query)
    npage = 0
    try:
        npage = int(query.pop('page', 0)[0])
    except (ValueError, IndexError, TypeError):
        pass

    # Convert to sorted tuple to mantain a coherent URL (it's good for tests)
    query = sorted([(k, v) for (k, v) in query.items()])
    while True:
        tmp = query + [('page', [npage])]
        npage += 1
        yield "http://spanishtracker.com/torrents.php?" + \
              parse.urlencode(tmp, doseq=True)


def process(buff):
    """
    Finds referentes to sources in buffer.
    Returns a list with sources infos
    """
    sources = []

    soup = bs4.BeautifulSoup(buff)
    table = soup.select("table table table table table")
    if not table:
        raise importers.ProcessException('Invalid markup')

    table = table[0]

    for tr in table.findAll('tr')[2:]:
        fields = tr.findAll('td')

        # Build URI and get title from col 1
        try:
            title = fields[1].find('a').text
            hash_string = re.findall(
                r'([0-9a-f]{40})',
                fields[1].find('a')['href'],
                re.IGNORECASE)[0]
        except IndexError:
            raise importers.ProcessException('Invalid markup')

        magnet = _MAGNET_STR.format({
            'hash_string': hash_string,
            'name': parse.quote_plus(title)
        })

        # Get added date
        timestamp = int(time.mktime(time.strptime(fields[5].text, '%d/%m/%Y')))

        # Size
        try:
            m = re.findall('([0-9\.]+) ([GMK])B', fields[6].text)[0]
        except IndexError:
            raise importers.ProcessException('Invalid markup')

        if len(m) != 2:
            raise importers.ProcessException('Invalid markup')

        size = int(float(m[0]) * _SIZE_TABLE[m[1]])

        type_ = None
        if re.findall(r'(cap\.|hdtv|temporada)', title, re.IGNORECASE):
            type_ = 'episode'

        elif re.findall(r'(dvdrip|blurayrip|dvd\s*screener)',
                        title,
                        re.IGNORECASE):
            type_ = 'movie'

        seeds, leechs = None, None
        try:
            seeds = int(fields[7].text)
            leechs = int(fields[8].text)
        except ValueError:
            pass

        lang = 'spa'
        if re.findall(r'(espa.+?l.+?castellano)', title, re.IGNORECASE):
            lang = 'spa-ES'
        elif title.lower().find('latino'):
            lang = 'spa-MX'

        # Add source
        sources.append({
            'uri': magnet,
            'name': title,
            'timestamp': timestamp,
            'size': size,
            'language': lang,
            'seeds': seeds,
            'leechers': leechs,
            'type': type_})

    return sources
