# -*- coding: utf-8 -*-


import base64
import binascii
import hashlib
import re
from urllib import parse


import bencodepy
from appkit import logging


import arroyo.exc
from arroyo import (
    kit,
    models
)


class BackendError(arroyo.exc._BaseException):
    pass


class ResolveError(arroyo.exc._BaseException):
    pass


class Downloads:
    """Downloads API.

    Handles operations between core.Arroyo and the different downloaders.
    """

    def __init__(self, app):
        app.register_extension_point(Downloader)
        app.register_extension_class(DownloadSyncCronTask)
        app.register_extension_class(DownloadQueriesCronTask)
        app.signals.register('source-state-change')

        self.app = app
        self.logger = logging.getLogger('downloads')

    @property
    def backend(self):
        return self.app.get_extension(Downloader, self.backend_name)

    @property
    def backend_name(self):
        return self.app.settings.get('downloader')

    def add(self, source):
        assert isinstance(source, models.Source)

        if source.needs_postprocessing:
            self.app.importer.resolve_source(source)

        try:
            self.backend.add(source)
        except Exception as e:
            msg = "Downloader '{name}' error: {e}"
            msg = msg.format(name=self.backend_name, e=e)
            raise BackendError(msg, original_exception=e) from e

        source.state = models.Source.State.INITIALIZING

        if source.entity:
            if source.entity.selection:
                self.app.db.session.delete(source.entity.selection)
            source.entity.selection = source.entity.SELECTION_MODEL(
                source=source
            )

        self.app.db.session.commit()
        self.app.signals.send('source-state-change', source=source)

    def add_all(self, *sources):
        assert isinstance(sources, list)
        assert len(sources) > 0
        assert all([isinstance(x, models.Source) for x in sources])

        ret = []
        for src in sources:
            try:
                self.add(src)
                ret.append((src, True, None))
            except arroyo.exc_BaseException as e:
                ret.append((src, False, e))

        return ret

    def remove(self, *sources):
        """Remove (and delete from disk) one or more sources from backend."""

        assert \
            len(sources) > 0 and \
            all([isinstance(x, models.Source) for x in sources])

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
        """Build a dict with bidirectional mapping between known sources and
        backend objects.
        """

        table = {}

        for dler_item in self.backend.list():
            source = self.backend.translate_item(dler_item, self.app.db)

            # The downloader backend can have unrelated items
            # with nothing in common with us!
            if not source:
                msg = "Unrelated item found: '{item}'"
                msg = msg.format(item=str(dler_item))
                self.logger.debug(msg)
                continue

            assert source not in table

            table[source] = dler_item
            table[dler_item] = source

        return table

    def list(self):
        """Return a list of models.Source of current downloads.

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

    def get_info(self, source=None):
        table = {}

        for backend_item in self.backend.list():
            matching_source = self.backend.translate_item(backend_item,
                                                          self.app.db)
            if not matching_source:
                continue

            table[matching_source] = backend_item
            if source and source == matching_source:
                break

        info_table = {}
        for (source, item) in table.items():
            info = self.backend.get_info(item)
            info_table[source] = DownloadInfo(**info)

        if source:
            return info_table[source]
        else:
            return info_table


class Downloader(kit.Extension):
    def add(self, source, **kwargs):
        raise NotImplementedError()

    def remove(self, source, **kwargs):
        raise NotImplementedError()

    def list(self, **kwargs):
        raise NotImplementedError()

    def get_state(self, source, **kwargs):
        raise NotImplementedError()

    def translate_item(self, backend_obj, database_interface):
        raise NotImplementedError()

    def get_info(self, backend_obj):
        raise NotImplementedError()


class DownloadInfo:
    def __init__(self, eta=None, files=None, location=None, progress=None):
        self.eta = eta
        self.files = files
        self.location = location
        self.progress = progress or 0.0


class DownloadSyncCronTask(kit.Task):
    __extension_name__ = 'download-sync'
    INTERVAL = '5M'

    def execute(self, app):
        app.downloads.sync()


class DownloadQueriesCronTask(kit.Task):
    __extension_name__ = 'download-queries'
    INTERVAL = '3H'

    def execute(self, app):
        queries = app.selector.queries_from_config()
        for q in queries:
            matches = app.selector.matches(q)
            srcs = app.selector.select(matches)

            if srcs is None:
                continue

            for src in srcs:
                try:
                    app.downloads.add(src)
                except Exception as e:
                    app.logger.error(str(e))
