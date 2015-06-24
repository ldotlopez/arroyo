import base64
import binascii
import re
from urllib import parse

from arroyo import models, selector
import arroyo.exc


class Downloads:
    """Downloads API.

    Handles operations between core.Arroyo and the different downloaders.
    """
    def __init__(self, app):
        app.signals.register('source-state-change')

        self._app = app
        self._logger = app.logger.getChild('downloads-manager')

    def get_queries(self):
        return {name: selector.Query(**params) for (name, params) in
                self._app.config_subdict('query').items()}

    def _get_backend(self):
        name = self._app.settings.get('downloader')
        return self._app.get_extension('downloader', name)

    def add(self, *sources):
        backend = self._get_backend()

        for src in sources:
            backend.do_add(src)
            src.state = models.Source.State.INITIALIZING

        self._app.db.session.commit()
        for src in sources:
            self._app.signals.send('source-state-change', source=src)

    def remove(self, *sources):
        backend = self._get_backend()

        translations = {}
        for dler_obj in backend.do_list():
            try:
                db_obj = backend.translate_item(dler_obj)
                translations[db_obj] = dler_obj
            except arroyo.exc.NoMatchingItem:
                pass

        for src in sources:
            try:
                backend.do_remove(translations[src])
                src.state = models.Source.State.NONE
                self._app.db.session.commit()

            except KeyError:
                self._logger.warning(
                    "No matching object in backend for '{}'".format(src))

    def list(self):
        backend = self._get_backend()

        ret = []

        for dler_obj in backend.do_list():
            # Filter out objects from downloader unknow for the db
            try:
                db_obj = backend.translate_item(dler_obj)
            except arroyo.exc.NoMatchingItem as e:
                msg = "No matching db object for {item}"
                self._logger.warn(msg.format(item=e))
                continue

            # Warn about unknow states
            try:
                dler_state = backend.get_state(dler_obj)
            except arroyo.exc.NoMatchingState as e:
                self._logger.warn(
                    "No matching state '{}' for {}".format(e.state, db_obj))
                continue

            ret.append(db_obj)
            db_state = db_obj.state
            if db_state != dler_state:
                db_obj.state = dler_state
                self._app.signals.send('source-state-change', source=db_obj)

        # Get for previous downloads manually removed
        for src in self._app.db.get_active():
            if src not in ret:
                src.state = models.Source.State.ARCHIVED
                self._app.signals.send('source-state-change', source=src)

        self._app.db.session.commit()

        return ret


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

    return (
        ':'.join([prefix, algo, urn_sha1]),
        ':'.join([prefix, algo, urn_base32])
    )


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
