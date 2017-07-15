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
        qs = qs.filter(
            models.Download.foreign_id.startswith(self.plugin_name + ':'))
        qs = qs.filter(models.Download.state != models.State.ARCHIVED)
        db_sources = [x.source for x in qs]

        plugin_ids = [self.add_plugin_prefix(x) for x in self.plugin.list()]

        # Warn about unknow plugin IDs
        # msg = "Unknow download detected in downloader plugin: {pid}"
        # db_ids = [src.download.foreign_id for src in db_sources]
        # for pid in set(plugin_ids) - set(db_ids):
        #     msg_ = msg.format(pid=pid)
        #     self.logger.warning(msg_)

        # Update state on db sources with info from plugin
        state_changes = []
        for src in db_sources:
            if src.download.foreign_id in plugin_ids:
                # src is present in downloader plugin
                plugin_id = self.strip_plugin_prefix(src.download.foreign_id)
                plugin_state = self.plugin.get_state(plugin_id)
                if plugin_state == src.download.state:
                    src.download.state = plugin_state
                    state_changes.append(src)

            else:
                # src was removed from downloader plugin
                if src.download.state >= models.State.SHARING:
                    src.download.state = models.State.ARCHIVED
                else:
                    self.app.db.session.delete(src.download)
                    src.download = None

                state_changes.append(src)

        # Notify about state changes
        for source in state_changes:
            self.app.signals.send('source-state-change', source=source)

        # Return current downloads for convenience
        return [
            src for src in db_sources
            if src.download and src.download.foreign_id in plugin_ids
        ]

    def add(self, source):
        self.sync()

        if source.download:
            raise DuplicatedDownloadError()

        foreign_id = self.plugin.add(source)
        foreign_id = '{name}:{fid}'.format(
            name=self.plugin_name, fid=foreign_id)
        source.download = models.Download(
            foreign_id=foreign_id, state=models.State.INITIALIZING)

        if source.entity and source.entity.selection is None:
            selection = source.entity.SELECTION_MODEL(source=source)
            source.entity.selection = selection

        self.app.db.session.commit()

    def list(self):
        return self.sync()

    def _remove(self, source, delete):
        downloads = self.list()

        if source not in downloads:
            raise DownloadNotFoundError()

        plugin_id = self.strip_plugin_prefix(source.download.foreign_id)
        if delete:
            ret = self.plugin.cancel(plugin_id)
        else:
            ret = self.plugin.archive(plugin_id)

        if ret is not True:
            msg = ("Invalid API usage from downloader plugin «{name}». "
                   "Should return True or raise an Exception but got '{ret}'")
            msg = msg.format(name=self.plugin_name, ret=repr(ret))
            raise arroyo.exc.PluginError(msg, None)

        if delete:
            # Delete download object
            self.app.db.session.delete(source.download)
            source.download = None

            # Delete selection if this source is the selection for its entity
            if (source.entity and
                    source.entity.selection and
                    (source.entity.selection.source == source)):
                self.app.db.session.delete(source.entity.selection)
                source.entity.selection = None

        else:
            # Just set the state
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
        info = self.plugin.get_info(plugin_id)

        return DownloadInfo(**info)

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
