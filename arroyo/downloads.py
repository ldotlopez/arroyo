# -*- coding: utf-8 -*-

import base64
import binascii
import hashlib
import re
from urllib import parse

import bencodepy
from arroyo import models, extension, cron


class Downloads:
    """Downloads API.

    Handles operations between core.Arroyo and the different downloaders.
    """
    def __init__(self, app):
        app.signals.register('source-state-change')
        app.register_extension('download-sync', DownloadSyncCronTask)
        app.register_extension('download-queries', DownloadQueriesCronTask)

        self.app = app
        self.logger = app.logger.getChild('downloads')
        self._backend = None

    @property
    def backend(self):
        if self._backend is None:
            name = self.app.settings.get('downloader')
            self._backend = self.app.get_extension(Downloader, name)

        return self._backend

    def add(self, *sources):
        """Adds (and starts) one or more sources to backend
        """
        if not sources:
            msg = "Missing parameter sources"
            raise TypeError(msg)

        for src in sources:
            self.backend.add(src)
            src.state = models.Source.State.INITIALIZING

            if src.entity:

                if src.entity.selection:
                    self.app.db.session.delete(src.entity.selection)

                src.entity.selection = \
                    src.entity.SELECTION_MODEL(source=src)

        self.app.db.session.commit()
        for src in sources:
            self.app.signals.send('source-state-change', source=src)

    def remove(self, *sources):
        """Remove (and delete) one or more sources from backend
        """
        if not sources:
            msg = "Missing parameter sources"
            raise TypeError(msg)

        translations = self.get_translations()

        for src in sources:
            try:
                self.backend.remove(translations[src])
            except KeyError:
                msg = "'{source}' is not in downloads"
                msg = msg.format(source=src)
                self.logger.warning(msg)
                continue

    def get_translations(self):
        """
        Build a dict with bidirectional mapping between
        known sources and backend objects.
        """
        table = {}
        for dler_item in self.backend.list():
            source = self.backend.translate_item(dler_item)

            # The downloader backend can have unrelated items
            # with nothing in common with us!
            if not source:
                msg = "Unrelated item found: '{item}'"
                msg = msg.format(item=dler_item)
                self.logger.debug(msg)
                continue

            assert source not in table

            table[source] = dler_item
            table[dler_item] = source

        return table

    def list(self):
        """Return a list of models.Source of current downloads

        Note: internally downloads.Downloader uses the method
        downloads.Downloader.sync which emits signals and has side effects on
        the database.
        """
        return self.sync()['downloads']

    def sync(self):
        """Update database information with backend data.

        Emits signal 'source-state-change' for each updated models.Source
        """
        translations = self.get_translations()
        active_downloads = [x for x in translations
                            if isinstance(x, models.Source)]
        active_sources = self.app.db.get_active()

        changes = []

        # Check for state-changes
        for src in active_downloads:
            backend_state = self.backend.get_state(translations[src])
            if src.state != backend_state:
                src.state = backend_state
                self.app.signals.send('source-state-change', source=src)
                changes.append(src)

        # Check for missing sources
        for src in set(active_sources) - set(active_downloads):
            src.state = models.Source.State.ARCHIVED
            self.app.signals.send('source-state-change', source=src)
            changes.append(src)

        self.app.db.session.commit()

        return {
            'changes': changes,
            'downloads': active_downloads,
        }


class Downloader(extension.Extension):
    def add(self, source, **kwargs):
        raise NotImplementedError()

    def remove(self, source, **kwargs):
        raise NotImplementedError()

    def list(self, **kwargs):
        raise NotImplementedError()

    def get_state(self, source, **kwargs):
        raise NotImplementedError()

    def translate_item(self, backend_obj):
        raise NotImplementedError()


class DownloadSyncCronTask(cron.CronTask):
    NAME = 'download-sync'
    INTERVAL = '5M'

    def run(self):
        self.app.downloads.sync()
        super().run()


class DownloadQueriesCronTask(cron.CronTask):
    NAME = 'download-queries'
    INTERVAL = '3H'

    def run(self):
        specs = self.app.selector.get_queries_specs()
        for spec in specs:
            matches = self.app.selector.matches(spec)
            srcs = self.app.selector.select(matches)

            if srcs is None:
                continue

            for src in srcs:
                self.app.downloads.add(src)

        super().run()


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
    """Check if urn matches sha1 urn: scheme
    """

    return re.match('^urn:(.+?):[A-F0-9]{40}$', urn, re.IGNORECASE) is not None


def is_base32_urn(urn):
    """Check if urn matches base32 urn: scheme
    """

    return re.match('^urn:(.+?):[A-Z2-7]{32}$', urn, re.IGNORECASE) is not None


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
        'xl': metadata.get(b'info', {}).get(b'length', b'').decode('utf-8')
    }

    magnet = 'magnet:?xt=urn:btih:{b32hash}&{params}'.format(
        b32hash=info.pop('b32hash'),
        params=parse.urlencode(info)
    )

    return magnet


def magnet_from_torrent_file(torrent_file):
    with open(torrent_file, 'rb') as fh:
        return magnet_from_torrent_data(fh.read())


def parse_magnet(magnet_url):
    """Parse magnet link
    """

    p = parse.urlparse(magnet_url)
    if p.scheme != 'magnet':
        msg = "Invalid magnet link: '{magnet}'"
        msg = msg.format(magnet=magnet_url)
        raise ValueError(msg)

    qs = parse.parse_qs(p.query)
    return qs


def rewrite_uri(uri):
    """Rewrites URI (magnet) using sha1sum ID
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
