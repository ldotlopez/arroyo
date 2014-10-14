# -*- coding: utf-8 -*-
# [SublimeLinter pep8-max-line-length:119]
# vim: set fileencoding=utf-8 :

import time
import feedparser


NAME = "The Pirate Bay (RSS parser)"
BASE_URL = 'http://rss.thepiratebay.se/100'


def url_generator(url=None):
    """Generates URLs for the current website,
    TPB doesn't support pagination on feeds
    """
    if url is None:
        url = BASE_URL

    yield url
    raise StopIteration


def process(buff):
    def _build_source(entry):
        return {
            'uri': entry['link'],
            'name': entry['title'],
            'timestamp': int(time.mktime(entry['published_parsed'])),
            'size': int(entry['contentlength'])
        }

    return [_build_source(s) for s in feedparser.parse(buff)['entries']]
