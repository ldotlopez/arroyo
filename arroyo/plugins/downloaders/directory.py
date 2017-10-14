# -*- coding: utf-8 -*-

# Copyright (C) 2017 Luis López <luis@cuarentaydos.com>
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


from arroyo import (
    bittorrentlib,
    models,
    pluginlib
)

import os
from urllib import parse


import asyncio
from appkit import utils


SETTINGS_NS = 'plugins.downloaders.directory'
VARIABLES_NS = 'downloaders.directory'


class DirectoryDownloader(pluginlib.Downloader):
    __extension_name__ = 'directory'

    def __init__(self, app, *args, **kwargs):
        super().__init__(app, *args, **kwargs)

        settings = app.settings

        storage_path = str(settings.get(SETTINGS_NS + '.storage-path', ''))
        if not storage_path:
            storage_path = utils.user_path(utils.UserPathType.DATA,
                                           name='downloads')

        os.makedirs(storage_path, exist_ok=True)

        self.storage_path = storage_path
        self.sess = self.app.db.session

    def id_for_source(self, source):
        return "{name}-{urn}".format(
            name=source.name,
            urn=source.urn.split(':')[2])

    def filepath_for_id(self, id_):
        return "{storage}/{id}.torrent".format(
            storage=self.storage_path,
            id=id_)

    def add(self, source):
        id_ = self.id_for_source(source)

        buff = self._fetch_torrent(source.uri)
        self._write_torrent(id_, buff)

        return id_

    def cancel(self, id_):
        self._remove_torrent(id_)
        return True

    def archive(self, id_):
        self._remove_torrent(id_)
        return True

    def list(self):
        torrents = os.listdir(self.storage_path)
        torrents = (self.storage_path + '/' + name for name in torrents)
        torrents = filter(
            lambda path: os.path.isfile(path) and path.endswith('torrent'),
            torrents)
        torrents = map(
            lambda x: x.split('/')[-1][:-8],
            torrents)  # Basename without extension
        return list(torrents)

    def get_state(self, id_):
        if os.path.exists(self.filepath_for_id(id_)):
            return models.State.INITIALIZING
        else:
            return models.State.ARCHIVED

    def get_info(self, tr_obj):
        return {}

    # FIXME: Make this method stateless for future parallelization
    def _fetch_torrent(self, magnet):
        parsed = parse.urlparse(magnet)
        params = parse.parse_qs(parsed.query)
        urn = bittorrentlib.normalize_urn(params['xt'][0])
        if not bittorrentlib.is_sha1_urn(urn):
            raise ValueError(urn)

        sha1hash = urn.split(':')[2]

        api = 'http://itorrents.org/torrent/{uc_hash}.torrent'
        url = api.format(uc_hash=sha1hash.upper())

        fut = asyncio.ensure_future(self.app.fetcher.fetch(url))
        loop = asyncio.get_event_loop()
        loop.run_until_complete(fut)

        return fut.result()

    def _write_torrent(self, id_, buff):
        filepath = self.filepath_for_id(id_)
        with open(filepath, 'wb') as fh:
            fh.write(buff)

    def _remove_torrent(self, id_):
        filepath = self.filepath_for_id(id_)
        os.unlink(filepath)


__arroyo_extensions__ = [
    DirectoryDownloader
]
