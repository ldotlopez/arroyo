import base64
import binascii
import hashlib
import re
from urllib import parse


import bencodepy


def is_sha1_urn(urn):
    """Check if urn matches sha1 urn: scheme
    """

    return re.match('^urn:(.+?):[A-F0-9]{40}$', urn, re.IGNORECASE) is not None


def is_base32_urn(urn):
    """Check if urn matches base32 urn: scheme
    """

    return re.match('^urn:(.+?):[A-Z2-7]{32}$', urn, re.IGNORECASE) is not None


def normalize_urn(urn):
    prefix, func, hash = urn.split(':', 2)
    if prefix != 'urn' or func != 'btih':
        msg = 'Unknow urn configuration: {urn}'
        msg = msg.format(urn=urn)
        raise ValueError(msg)

    if is_sha1_urn(urn):
        return urn.lower()

    elif is_base32_urn(urn):
        hash = hash.upper()
        hash = base64.b32decode(hash)
        hash = binascii.hexlify(hash)
        hash = hash.decode('ascii')
        hash = hash.upper()
        return '{prefix}:{func}:{hash}'.format(
            prefix=prefix,
            func=func,
            hash=hash)

    else:
        msg = "Unknow encoding: '{urn}'"
        msg = msg.format(urn=urn)
        raise ValueError(msg)


def magnet_from_torrent_data(torrent_data):
    def flatten(x):
        if isinstance(x, list):
            for y in x:
                yield from flatten(y)
        else:
            yield x

    metadata = bencodepy.decode(torrent_data)

    hash_contents = bencodepy.encode(metadata[b'info'])
    digest = hashlib.sha1(hash_contents).digest()
    b32hash = base64.b32encode(digest)

    info = {
        'b32hash':  b32hash.decode('utf-8'),
        'tr': [x.decode('utf-8') for x in
               flatten(metadata.get(b'announce-list', []) or
                       [metadata[b'announce']])],
        'dn': metadata.get(b'info', {}).get(b'name', b'').decode('utf-8'),
        'xl': metadata.get(b'info', {}).get(b'length')
    }
    try:
        info['xl'] = int(info['xl'])
    except ValueError:
        del info['xl']

    magnet = 'magnet:?xt=urn:btih:{b32hash}&{params}'.format(
        b32hash=info.pop('b32hash'),
        params=parse.urlencode(info)
    )

    return magnet


def magnet_from_torrent_file(torrent_file):
    with open(torrent_file, 'rb') as fh:
        return magnet_from_torrent_data(fh.read())


def mock_urn(name):
    assert name and isinstance(name, str)

    digest = hashlib.sha1(name.encode('utf-8')).hexdigest()
    return 'urn:btih:' + digest


def mock_uri(name):
    assert name and isinstance(name, str)

    urn = mock_urn(name)
    return 'magnet:?dn={name}&xt={urn}'.format(
        name=parse.quote_plus(name),
        urn=urn)
