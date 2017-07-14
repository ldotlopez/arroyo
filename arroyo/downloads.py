# -*- coding: utf-8 -*-

# Copyright (C) 2015 Luis López <luis@cuarentaydos.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301,
# USA.


from appkit import loggertools
from appkit.db import sqlalchemyutils as sautils


import arroyo.exc
from arroyo import (
    kit,
    models
)


class DuplicatedDownloadError(Exception):
    """Requested download already exists

    Raised by downloader plugins
    """
    pass


class DownloadNotFoundError(Exception):
    """Requested download doesn't exists

    Raised by downloader plugins
    """
    pass


class AlreadyDownloadedError(Exception):
    pass


class InvalidStateError(Exception):
    pass


class ResolveLazySourceError(Exception):
    """Lazy source can't be resolves

    Raised by arroyo.downloads
    """
    pass


class Downloader(kit.Extension):
    """Extension point for downloaders"""

    def add(self, source):
        """Adds source to download.

        Must return True on successful or raise an Exception on failure
        """
        raise NotImplementedError()

    def cancel(self, foreign_id):
        """Cancels foreign ID and deletes any possible file

        Must return True on successful or raise an Exception on failure
        """
        raise NotImplementedError()

    def archive(self, foreign_id):
        """Archives source to download, just remove it from downloader keeping
        any possible files

        Must return True on successful or raise an Exception on failure
        """
        raise NotImplementedError()

    def list(self):
        raise NotImplementedError()

    def get_state(self, foreign_id):
        raise NotImplementedError()

    def get_info(self, foreign_id):
        raise NotImplementedError()

    def id_for_source(self, source):
        """For tests. Returns an acceptable (even simulated or random) local ID
        for this source"""
        raise NotImplementedError()


class Downloads:
    def __init__(self, app):
        app.register_extension_point(Downloader)
        app.register_extension_class(DownloadSyncCronTask)
        app.register_extension_class(DownloadQueriesCronTask)
        app.signals.register('source-state-change')

        self._plugin = None
        self.app = app
        self.logger = loggertools.getLogger('downloads')
        self.plugin_name = self.app.settings.get('downloader')

    def strip_plugin_prefix(self, s):
        assert s.startswith(self.plugin_name + ':')
        return s.split(':', 1)[1]

    def add_plugin_prefix(self, s):
        assert not s.startswith(self.plugin_name + ':')
        return self.plugin_name + ':' + s

    @property
    def plugin(self):
        return self.app.get_extension(Downloader, self.plugin_name)

    def sync(self):
        qs = self.app.db.session.query(models.Download)
        qs = qs.filter(models.Download.foreign_id.startswith(self.plugin_name + ':'))
        qs = qs.filter(models.Download.state != models.State.ARCHIVED)
        db_sources = [x.source for x in qs]

        plugin_ids = [self.add_plugin_prefix(x) for x in self.plugin.list()]

        # Archive sources not in plugin
        changes = []
        for source in db_sources:
            if source.download.foreign_id not in plugin_ids:
                if source.download.state >= models.State.SHARING:
                    source.download.state = models.State.ARCHIVED
                else:
                    self.app.db.session.delete(source.download)
                    source.download = None
                changes.append(source)

            else:
                state = self.plugin.get_state(self.strip_plugin_prefix(source.download.foreign_id))
                if state != source.download.state:
                    source.download.state = state
                    changes.append(source)

        for plugin_id in set(plugin_ids) - set([x.download.foreign_id for x in db_sources]):
            self.logger.warning('unknow ' + plugin_id)

        self.app.db.session.commit()
        
        for source in changes:
            self.app.signals.send('source-state-change', source=source)
        
        ret = [x for x in db_sources if source.download and source.download.state != models.State.ARCHIVED]
        return ret

    def add(self, source):
        downloads = self.sync()

        if source.download:
            raise DuplicatedDownloadError()

        foreign_id = self.plugin.add(source)
        foreign_id = '{name}:{fid}'.format(name=self.plugin_name, fid=foreign_id)
        source.download = models.Download(foreign_id=foreign_id, state=models.State.INITIALIZING)
        self.app.db.session.commit()

    def list(self):
        return self.sync()

    def _remove(self, source, delete):
        downloads = self.list()

        if source not in downloads:
            raise DownloadNotFoundError()

        if delete:
            ret = self.plugin.cancel(self.strip_plugin_prefix(source.download.foreign_id))
        else:
            ret = self.plugin.archive(self.strip_plugin_prefix(source.download.foreign_id))
        
        if ret is not True:
            msg = ("Invalid API usage from downloader plugin «{name}». "
                   "Should return True or raise an Exception but got '{ret}'")
            msg = msg.format(name=self.plugin_name, ret=repr(ret))
            raise arroyo.exc.PluginError(msg, None)

        if delete:
            self.app.db.session.delete(source.download)
            source.download = None
        else:
            source.download.state = models.State.ARCHIVED    

        self.app.db.session.commit()

    def archive(self, source):
        self._remove(source, delete=False)

    def cancel(self, source):
        self._remove(source, delete=True)

    def get_info(self, source):
        if not source.download:
            raise DownloadNotFoundError()

        plugin_id = self.strip_plugin_prefix(source.download.foreign_id)
        return self.plugin.get_info(plugin_id)


    def add_all(self, sources):
        return self._generic_all_wrapper(self.add, sources)

    def archive_all(self, sources):
        return self._generic_all_wrapper(self.archive, sources)

    def cancel_all(self, sources):
        return self._generic_all_wrapper(self.cancel, sources)

    def _generic_all_wrapper(self, fn, args):
        ret = []

        for arg in args:
            try:
                ret.append(fn(arg))
            except SyntaxError:
                raise
            except Exception as e:
                ret.append(e)

        return ret

class _Downloads:
    """Downloads API.

    Handles operations between core.Arroyo and the different downloaders.
    """

    def __init__(self, app):
        app.register_extension_point(Downloader)
        app.register_extension_class(DownloadSyncCronTask)
        app.register_extension_class(DownloadQueriesCronTask)
        app.signals.register('source-state-change')

        self._plugin = None
        self.app = app
        self.logger = loggertools.getLogger('downloads')
        self.plugin_name = self.app.settings.get('downloader')
        
    @property
    def plugin(self):
        if self._plugin is None:
            self._plugin = self.app.get_extension(Downloader, self.plugin_name)

        return self._plugin

    def extract_plugin_name(self, foreign_id):
        return foreign_id.split(':', 2)

    def build_foreign_id(self, fid):
        if fid.startswith(self.plugin_name + ':'):
            raise ValueError(fid)

        return self.plugin_name + ':' + fid

    def add(self, source):
        # Check if source is already downloading within active plugin
        if (source.download and
                self.extract_plugin_name(source.download.foreign_id) == self.plugin_name):
            msg = "Source is already downloading"
            raise ValueError(source, msg)

        self._sync()

        foreign_id = self.plugin_name + ':' + self.plugin.add(source)

    def _sync(self):
        # Build db_downloads and plugin downloads
        db_downloads = set(self.app.db.session.query(models.Download))

        plugin_downloads = []
        translations = self.get_translations()
        for id_ in self.plugin.list():
            try:
                plugin_downloads.append(translations[id_].download)
            except KeyError:
                import ipdb; ipdb.set_trace(); pass

        plugin_downloads = set(plugin_downloads)

        # Update known download states from plugin info
        for download in plugin_downloads:
            plugin_state = self.plugin.get_state(download.foreign_id)
            if download.state != plugin_state:
                download.state = plugin_state
                self.app.signals.send('source-state-change',
                                      source=download.source)

        # What happend with downloads in progress not found in plugin
        # downloads?
        for download in db_downloads - plugin_downloads:
            source = download.source

            # If last known state was, at least, sharing we asume that user
            # removed it from download app and should be considered archived.
            # On the opposite case we asume that user cancel the download.

            if download.state >= models.State.SHARING:
                download.state = models.State.ARCHIVED
            else:
                self.app.db.session.delete(source.download)
                source.download = None

                if source.entity and source.entity.selection == source:
                    self.app.db.session.delete(source.entity.selection)
                    source.entity.selection = None

        self.app.db.session.commit()


class Downloads_:
    """Downloads API.

    Handles operations between core.Arroyo and the different downloaders.
    """

    def __init__(self, app):
        app.register_extension_point(Downloader)
        app.register_extension_class(DownloadSyncCronTask)
        app.register_extension_class(DownloadQueriesCronTask)
        app.signals.register('source-state-change')

        self.app = app
        self.logger = loggertools.getLogger('downloads')
        self.plugin_name = self.app.settings.get('downloader')
        self._plugin = None

    @property
    def plugin(self):
        if self._plugin is None:
            self._plugin = self.app.get_extension(Downloader, self.plugin_name)

        return self._plugin

    def downloads_for_current_plugin(self):
        qs = self.app.db.session.query(models.Download)
        qs = qs.filter(
            models.Download.foreign_id.startswith(self.plugin_name + ':')
        )
        return qs.all()

    def add_download(self, source, foreign_id):
        if source.download:
            msg = "Source already has a download attached"
            raise ValueError(source, msg)

        source.download = models.Download(
            foreign_id = self.plugin_name + ':' + foreign_id,
            source=source
        )
        self.app.db.add(source.download)
        self.app.db.commit()

    def remove_download(self, source_or_foreign_id):
        qs = self.app.db.session.query(models.Download)

        if isinstance(source_or_foreign_id, models.Source):
            source = source_or_foreign_id
            if source.download.state != models.State.NONE:
                msg = "Download must be stopped before remove"
                raise ValueError(source, msg)

            download = qs.filter(models.Source.source == source_or_foreign_id).one()

        elif isinstance(source_or_foreign_id, str):
            foreign_id = self.plugin_name + ':' + source_or_foreign_id
            download = qs.filter(models.Source.foreign_id==foreign_id).one()

        else:
            msg = "source_or_foreign_id must be a models.Source object or a string"
            raise TypeError(source_or_foreign_id, msg)

        download.source.download = None
        self.app.db.session.delete(download)
        self.app.db.session.commit()


    def add(self, source):
        assert isinstance(source, models.Source)
        self._sync()

        if source.download:
            raise DuplicatedDownloadError(source)

        if source.needs_postprocessing:
            try:
                self.app.importer.resolve_source(source)
            except ValueError as e:
                raise ResolveLazySourceError(source) from e

        ret = self.plugin.add(source)

        if not isinstance(ret, str) or ret == '':
            source.download = None
            msg = ("Invalid API usage from downloader plugin «{name}». "
                   "Should return the plugin foreign ID but got '{ret}'")
            msg = msg.format(name=self.plugin_name, ret=repr(ret))
            raise arroyo.exc.PluginError(msg, None)

        if source.download is None:
            source.download = models.Download(state=models.State.INITIALIZING)
        source.download.foreign_id = '{plugin}:{foreign_id}'.format(
            plugin=self.plugin_name, foreign_id=ret)

        if source.entity:
            if source.entity.selection:
                self.app.db.session.delete(source.entity.selection)
            source.entity.selection = source.entity.SELECTION_MODEL(
                source=source
            )

        self.app.db.session.commit()
        self.app.signals.send('source-state-change', source=source)

    def _remove(self, source, cancel=None, archive=None):
        # Check types
        if not (
                (cancel is None or isinstance(cancel, bool)) and
                (archive is None or isinstance(archive, bool))):
            msg = "cancel and archive should be None, True or False"
            raise ValueError(msg)

        if cancel is None and archive is None:
            msg = "cancel or archive parameter should be specified"
            raise ValueError(msg)

        if cancel is not None and archive is not None:
            msg = "only one of cancel or archive should be True"
            raise ValueError(msg)

        cancel = not archive

        self._sync()

        if not source.download:
            raise DownloadNotFoundError(source)

        if (source.download.state <= models.State.NONE or
                source.download.state >= models.State.ARCHIVED):
            raise InvalidStateError(source)

        dummy, foreign_id = source.download.foreign_id.split(':', 2)
        if cancel:
            ret = self.plugin.cancel(source.download.foreign_id)
        else:
            ret = self.plugin.archive(source.download.foreign_id)

        if not isinstance(ret, bool):
            msg = ("Invalid API usage from downloader plugin «{name}». "
                   "Should return a bool but got '{ret}'")
            msg = msg.format(name=self.plugin_name, ret=repr(ret))
            raise arroyo.exc.PluginError(msg, None)

        if not ret:
            msg = "Failed to remove download"
            raise arroyo.exc.PluginError(msg)

        if cancel:
            if source.entity:
                self.app.db.session.delete(source.entity.selection)
                source.entity.selection = None

            self.app.db.session.delete(source.download)
            source.download = None

        else:
            source.download.state = models.State.ARCHIVED

        self.app.db.session.commit()
        self.app.signals.send('source-state-change', source=source)

    def cancel(self, source):
        self._remove(source, cancel=True)
        self.app.signals.send('source-state-change', source=source)

    def archive(self, source):
        self._remove(source, archive=True)
        self.app.signals.send('source-state-change', source=source)

    def add_all(self, sources):
        return self._generic_all_wrapper(self.add, sources)

    def archive_all(self, ids):
        return self._generic_all_wrapper(self.archive, ids)

    def cancel_all(self, ids):
        return self._generic_all_wrapper(self.cancel, ids)

    def _generic_all_wrapper(self, fn, args):
        ret = []

        for arg in args:
            try:
                ret.append(fn(arg))
            except SyntaxError:
                raise
            except Exception as e:
                ret.append(e)

        return ret

    def get_translations(self):
        """Build a dict with bidirectional mapping between known sources and
        backend objects.
        """
        db_downloads = self.app.db.session.query(models.Download)

        table = {
            x.source: x.foreign_id
            for x in db_downloads
        }
        table.update({value: key for (key, value) in table.items()})

        return table

    def list(self, sync=True):
        """Return a list of models.Source of current downloads.

        Note: internally downloads.Downloader uses the method
        downloads.Downloader.sync which emits signals and has side effects on
        the database.
        """
        self._sync()

        qs = self.app.db.session.query(models.Download)
        qs = qs.filter(~models.Download.state.in_([
                models.State.NONE, models.State.ARCHIVED]))
        return [x.source for x in qs]

    def _sync(self):
        # Build db_downloads and plugin downloads
        db_downloads = set(self.app.db.session.query(models.Download))

        plugin_downloads = []
        translations = self.get_translations()
        for id_ in self.plugin.list():
            try:
                plugin_downloads.append(translations[id_].download)
            except KeyError:
                import ipdb; ipdb.set_trace(); pass

        plugin_downloads = set(plugin_downloads)

        # Update known download states from plugin info
        for download in plugin_downloads:
            plugin_state = self.plugin.get_state(download.foreign_id)
            if download.state != plugin_state:
                download.state = plugin_state
                self.app.signals.send('source-state-change',
                                      source=download.source)

        # What happend with downloads in progress not found in plugin
        # downloads?
        for download in db_downloads - plugin_downloads:
            source = download.source

            # If last known state was, at least, sharing we asume that user
            # removed it from download app and should be considered archived.
            # On the opposite case we asume that user cancel the download.

            if download.state >= models.State.SHARING:
                download.state = models.State.ARCHIVED
            else:
                self.app.db.session.delete(source.download)
                source.download = None

                if source.entity and source.entity.selection == source:
                    self.app.db.session.delete(source.entity.selection)
                    source.entity.selection = None

        self.app.db.session.commit()

    def get_info(self, source):
        foreign_id = self.get_translations()[source]
        return DownloadInfo(**self.plugin.get_info(foreign_id))


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

        downloads = []

        for (name, query) in queries:
            matches = app.selector.matches(query)
            srcs = app.selector.select(matches)

            if srcs is None:
                continue

            downloads.extend(srcs)

        if not downloads:
            return

        for ret in app.downloads.add_all(downloads):
            if isinstance(ret, Exception):
                app.logger.error(str(ret))
