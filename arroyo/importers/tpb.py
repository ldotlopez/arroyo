# -*- coding: utf-8 -*-
# [SublimeLinter pep8-max-line-length:119]
# vim: set fileencoding=utf-8 :

import re

import bs4
from ldotcommons.utils import utcnow_timestamp

NAME = "The Pirate Bay"
BASE_URL = 'http://thepiratebay.com/recent/0/'

_SIZE_TABLE = {'K': 10 ** 3, 'M': 10 ** 6, 'G': 10 ** 9}


def url_generator(url=None):
    if url is None:
        url = BASE_URL

    # And '/' at the end
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


def process(buff):
    soup = bs4.BeautifulSoup(buff)
    trs = soup.select('table > tr')[:-1]

    sources = []
    for tr in trs:
        details = tr.select('font.detDesc')[0].text

        (amount, suffix) = re.findall(r'([0-9\.]+)\s([GMK])iB', details, re.IGNORECASE)[0]
        size = int(float(amount) * _SIZE_TABLE[suffix])

        sources.append({
            'name': tr.findAll('a')[2].text,
            'uri': tr.findAll('a')[3]['href'],
            'size': size,
            'timestamp': utcnow_timestamp(),
            'seeds': int(tr.findAll('td')[-2].text),
            'leechers': int(tr.findAll('td')[-1].text)
        })

    return sources
