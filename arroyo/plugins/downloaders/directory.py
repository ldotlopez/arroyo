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

    def add(self, source, **kwargs):
        filepath = self.storage_path + '/' + source.name + '.torrent'
        with open(filepath, 'wb') as fh:
            fh.write(self._torrent_file_for_magnet(source.uri))

    def remove(self, item):
        os.unlink(item)

    def list(self):
        torrents = os.listdir(self.storage_path)
        torrents = (self.storage_path + '/' + name for name in torrents)
        torrents = filter(
            lambda path: os.path.isfile(path) and path.endswith('torrent'),
            torrents)

        return list(torrents)

    def get_state(self, native_item):
        if os.path.exists(native_item):
            return models.State.INITIALIZING
        else:
            return models.State.ARCHIVED

    def get_info(self, tr_obj):
        raise NotImplementedError()

    def translate_item(self, native_item, db):
        uri = bittorrentlib.magnet_from_torrent_file(native_item)
        params = parse.parse_qs(parse.urlparse(uri).query)
        urn = bittorrentlib.normalize_urn(params['xt'][-1])

        return db.session.query(
            models.Source
        ).filter(
            models.Source.urn == urn
        ).one()

    # Keep this method static and stateless for future parallelization
    @staticmethod
    def _torrent_file_for_magnet(magnet):
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


__arroyo_extensions__ = [
    DirectoryDownloader
]
