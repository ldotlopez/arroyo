# -*- coding: utf-8 -*-
# [SublimeLinter pep8-max-line-length:119]
# vim: set fileencoding=utf-8 :

import binascii
import base64
import re
from urllib import parse


class NoMatchingState(Exception):

    def __init__(self, state, *args, **kwargs):
        self.state = state
        super(NoMatchingState, self).__init__(*args, **kwargs)


class NoMatchingItem(Exception):

    def __init__(self, item, *args, **kwargs):
        self.item = item
        super(NoMatchingItem, self).__init__(*args, **kwargs)


class BackendError(Exception):

    def __init__(self, e, *args, **kwargs):
        self.exception = e
        super(BackendError, self).__init__(*args, **kwargs)


def calculate_urns(urn):
    """
    Returns all equivalent urns in different encodings
    Returns (sha1 urn, base32 urn)
    """

    (urn_sha1, urn_base32) = (None, None)

    prefix, algo, id_ = urn.split(':', 3)

    if is_sha1_urn(urn):
        urn_sha1 = id_
        urn_base32 = base64.b32encode(binascii.unhexlify(id_)).decode('ascii')

    elif is_base32_urn(urn):
        urn_sha1 = binascii.hexlify(base64.b32decode(id_)).decode('ascii')
        urn_base32 = id_

    else:
        raise Exception("Unknow enconding for '{}'".format(urn))

    return (':'.join([prefix, algo, urn_sha1]), ':'.join([prefix, algo, urn_base32]))


def is_sha1_urn(urn):
    return re.match('^urn:(.+?):[A-F0-9]{40}$', urn, re.IGNORECASE) is not None


def is_base32_urn(urn):
    return re.match('^urn:(.+?):[A-Z2-7]{32}$', urn, re.IGNORECASE) is not None


def parse_magnet(magnet_url):
    p = parse.urlparse(magnet_url)
    if p.scheme != 'magnet':
        raise Exception("Invalid magnet link: '{}'".format(magnet_url))

    qs = parse.parse_qs(p.query)
    return qs


def rewrite_uri(uri):
    """
    Rewrites URI (magnet) using sha1sum ID
    """
    def _rewrite_pair(x):
        (k, v) = x
        if k == 'xt':
            return (k, calculate_urns(v)[0])
        else:
            return (k, parse.quote_plus(v))

    parsed = parse.parse_qsl(parse.urlparse(uri).query)
    parsed_map = map(_rewrite_pair, parsed)
    query = '&'.join(['{}={}'.format(k, v) for (k, v) in parsed_map])

    return 'magnet:?' + query
