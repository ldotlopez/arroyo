import base64
import binascii
import re
from urllib import parse

from arroyo import models
import arroyo.exc


class Downloads:
    """Downloads API.

    Handles operations between core.Arroyo and the different downloaders.
    """
    def __init__(self, app):
        app.signals.register('source-state-change')

        self._app = app
        self._logger = app.logger.getChild('downloads')
        self._backend = None

    @property
    def backend(self):
        if self._backend is None:
            name = self._app.settings.get('downloader')
            self._backend = self._app.get_extension('downloader', name)

        return self._backend

    def add(self, *sources):
        if not sources:
            msg = "Missing parameter sources"
            raise TypeError(msg)

        for src in sources:
            self.backend.add(src)
            src.state = models.Source.State.INITIALIZING

        self._app.db.session.commit()
        for src in sources:
            self._app.signals.send('source-state-change', source=src)

    def remove(self, *sources):
        if not sources:
            msg = "Missing parameter sources"
            raise TypeError(msg)

        translations = {}
        for dler_obj in self.backend.list():
            try:
                db_obj = self.backend.translate_item(dler_obj)
                translations[db_obj] = dler_obj
            except arroyo.exc.NoMatchingItem:
                pass

        for src in sources:
            try:
                self.backend.remove(translations[src])
                src.state = models.Source.State.NONE
                self._app.db.session.commit()

            except KeyError:
                self._logger.warning(
                    "No matching object in backend for '{}'".format(src))

    @property
    def translation_table(self):
        table = {}
        for dler_item in self.backend.list():
            source = self.backend.translate_item(dler_item)

            table[source] = dler_item
            table[dler_item] = source

        return table

    def list(self):
        ret = []

        for dler_item in self.backend.list():

            # Filter out objects from downloader unknow for the db
            source = self.backend.translate_item(dler_item)
            if not source:
                msg = "No matching db object for {item}"
                msg = msg.format(item=dler_item)
                self._logger.warning(msg)
                continue

            # Warn about unknow states
            backend_state = self.backend.get_state(dler_item)
            if backend_state is None:
                msg = "Unknow state for {item}"
                msg = msg.format(item=dler_item)
                self._logger.warning(msg)
                continue

            ret.append(source)

            if source.state != backend_state:
                source.state = backend_state
                self._app.signals.send('source-state-change', source=source)

        # Get for previous downloads manually removed
        for src in self._app.db.get_active():
            if src not in ret:
                src.state = models.Source.State.ARCHIVED
                self._app.signals.send('source-state-change', source=src)

        self._app.db.session.commit()

        return ret


def calculate_urns(urn):
    """Returns all equivalent urns in different encodings

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
        msg = "Unknow enconding for '{urn}'"
        msg = msg.format(urn=urn)
        raise ValueError(msg)

    return (
        ':'.join([prefix, algo, urn_sha1]),
        ':'.join([prefix, algo, urn_base32])
    )


def is_sha1_urn(urn):
    """Check if urn matches sha1 urn: scheme"""
    return re.match('^urn:(.+?):[A-F0-9]{40}$', urn, re.IGNORECASE) is not None


def is_base32_urn(urn):
    """Check if urn matches base32 urn: scheme"""
    return re.match('^urn:(.+?):[A-Z2-7]{32}$', urn, re.IGNORECASE) is not None


def parse_magnet(magnet_url):
    """Parse magnet link"""
    p = parse.urlparse(magnet_url)
    if p.scheme != 'magnet':
        msg = "Invalid magnet link: '{magnet}'"
        msg = msg.format(magnet=magnet_url)
        raise ValueError(msg)

    qs = parse.parse_qs(p.query)
    return qs


def rewrite_uri(uri):
    """Rewrites URI (magnet) using sha1sum ID"""
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


#
# Old sync function (now integrated in Downloader.list but left here for
# reference or future reusage
#

# def sync(self):
#     ret = {'sources-state-change': []}
#
#     downloads = set(self.list())
#     actives = set(self._app.db.get_active())
#
#     for source in actives - downloads:
#         source.state = models.Source.State.ARCHIVED
#         ret['sources-state-change'].append(source)
#         self._app.signals.send('source-state-change', source=source)
#
#     self._app.db.session.commit()
#
#     return ret
