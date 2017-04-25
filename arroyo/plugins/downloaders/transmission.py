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


# Documentation for transmissionrpc:
# https://pythonhosted.org/transmissionrpc/reference/transmissionrpc.html


from arroyo import (
    bittorrentlib,
    pluginlib
)


from urllib import parse


import transmissionrpc
from appkit import (
    loggertools,
    store
)
from sqlalchemy import orm


# Support for monkey patch transmissionrpc

def tranmissionrpc_torrent_files(torrent):
    files = torrent.files().values()
    if not files:
        return []

    return [x['name'] for x in files]


def tranmissionrpc_torrent___str__(torrent):
    files = tranmissionrpc_torrent_files(torrent)
    if not files:
        return repr(torrent)

    root = [x.split('/')[0] for x in files][0]

    return root


transmissionrpc.torrent.Torrent.__str__ = tranmissionrpc_torrent___str__


models = pluginlib.models


SETTINGS_NS = 'plugins.downloaders.transmission'
STATE_MAP = {
    'checking': models.State.INITIALIZING,
    'check pending': models.State.INITIALIZING,
    'download pending': models.State.QUEUED,
    'downloading': models.State.DOWNLOADING,
    'seeding': models.State.SHARING,
    # other states need more logic
}
TRANSMISSION_API_ERROR_MSG = (
    "Error while trying to communicate with transmission: '{message}'"
)


class TransmissionDownloader(pluginlib.Downloader):
    __extension_name__ = 'transmission'

    def __init__(self, app, *args, **kwargs):
        super().__init__(app, *args, **kwargs)
        settings = app.settings

        self.logger = loggertools.getLogger('transmission')
        settings.add_validator(self.settings_validator)

        try:
            s = settings.get(SETTINGS_NS, default={})
            self.api = transmissionrpc.Client(
                address=s.get('address', 'localhost'),
                port=s.get('port', 9091),
                user=s.get('user', None),
                password=s.get('password', None)
            )
            self.shield = {
                'urn:btih:' + x.hashString: x
                for x in self.api.get_torrents()}

        except transmissionrpc.error.TransmissionError as e:
            msg = TRANSMISSION_API_ERROR_MSG.format(message=e.original.message)
            raise pluginlib.exc.PluginError(msg, e) from e

    def add(self, source, **kwargs):
        urn = bittorrentlib.normalize_urn(source.urn)

        # FIXME: Should we raise DuplicatedDownloadError?
        if urn in self.shield:
            # return self.shield[urn]
            return

        try:
            ret = self.api.add_torrent(source.uri)

        except transmissionrpc.error.TransmissionError as e:
            msg = TRANSMISSION_API_ERROR_MSG.format(message=e.original.message)
            raise pluginlib.exc.PluginError(msg, e) from e

        self.shield[urn] = ret
        # return ret

    def remove(self, item):
        self.shield = {urn: i for (urn, i) in self.shield.items() if i != item}

        # FIXME: Should we raise DownloadNotFoundError if item is not found?

        try:
            return self.api.remove_torrent(item.id, delete_data=True)

        except transmissionrpc.error.TransmissionError as e:
            msg = TRANSMISSION_API_ERROR_MSG.format(message=e.original.message)
            raise pluginlib.exc.PluginError(msg, e) from e

    def list(self):
        return self.api.get_torrents()

    def get_state(self, tr_obj):
        # stopped status can mean:
        # - if progress is less that 100, source is paused
        # - if progress is 100, source can be paused or seeding completed
        #   isFinished attr can handle this
        if tr_obj.status == 'stopped':
            if tr_obj.progress < 100:
                return models.State.PAUSED
            else:
                return models.State.DONE

        state = tr_obj.status

        if state not in STATE_MAP:
            msg = "Unknown state «{state}»."
            msg = msg.format(state=state)
            raise pluginlib.exc.SelfCheckError(msg)

        return STATE_MAP[state]

    def get_info(self, tr_obj):
        ret = {
            'files': tranmissionrpc_torrent_files(tr_obj)
        }
        if ret['files']:
            ret['location'] = tr_obj.downloadDir + \
                ret['files'][0].split('/')[0]

        for attr in ['eta', 'progress']:
            try:
                value = getattr(tr_obj, attr)
            except ValueError:
                value = None

            ret[attr] = value

        return ret

    def translate_item(self, tr_obj, db):
        urn = parse.parse_qs(
            parse.urlparse(tr_obj.magnetLink).query).get('xt')[0]

        urn = bittorrentlib.normalize_urn(urn)

        # Try to match urn in any form
        ret = None
        try:
            # Use like here for case-insensitive filter
            q = db.session.query(models.Source)
            q = q.filter(models.Source.urn.like(urn))
            ret = q.one()

        except orm.exc.MultipleResultsFound:
            msg = "Multiple results found for urn '{urn}'"
            msg = msg.format(urn=urn)
            self.logger.critical(msg)
            raise

            # # This code was used to workaroung this exception.
            # # Delete it since its better to fix this bug!
            # # There shouldn't be multiple results !!
            # # Trying to do my best
            # by_state = q.filter(models.Source.is_active is True)
            # if by_state.count() == 1:
            #     msg = ("Exception saved using state property but this "
            #            "is a bug")
            #     self.logger.error(msg)
            #     ret = by_state.first()
            #     break
            # else:
            #     msg = ("Unable to rescue invalid state. Multiple "
            #            "sources found, fix this.")
            #     self.logger.error(msg)

        except orm.exc.NoResultFound:
            pass

        if not ret:
            # Important note here
            # We ended here because backend returned an unknow item from its
            # list method. This is *NOT A BUG*. User can have another
            # downloads, get over it.

            # msg = ("Missing urn '{urn}'\n"
            #        "This is a bug, a real bug. Fix it. Now")
            # msg = msg.format(urn=urns[0])
            # self.logger.error(msg)
            return None

        # Attach some fields to item
        for k in ('progress', ):
            try:
                setattr(ret, k, getattr(tr_obj, k))
            except:
                setattr(ret, k, None)

        return ret

    @staticmethod
    def settings_validator(key, value):
        if not key.startswith(SETTINGS_NS):
            return value

        prop = key[len(TransmissionDownloader._SETTINGS_NS)+1:]

        if prop == 'enabled':
            if not isinstance(value, bool):
                raise store.ValidationError(key, value, 'Must a bool')
            else:
                return value

        if prop in ['address', 'user', 'password']:
            if not isinstance(value, str):
                raise store.ValidationError(key, value, 'Must a bool')
            else:
                return value

        if prop == 'port':
            if not isinstance(value, int):
                raise store.ValidationError(key, value, 'Must be a int')
            else:
                return value

        else:
            raise store.ValidationError(key, value, 'Unknow property')


__arroyo_extensions__ = [
    TransmissionDownloader
]
