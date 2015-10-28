# -*- coding: utf-8 -*-

from arroyo import plugin
from arroyo.plugin.tools import downloads
models = plugin.models

from urllib import parse

from sqlalchemy import orm
import transmissionrpc
from ldotcommons import store


_SETTINGS_NS = 'plugin.transmission'


def settings_validator(key, value):
    k = key[len(_SETTINGS_NS)+1:]

    if k == 'enabled':
        return store.cast_value(value, bool)

    if k in ['address', 'user', 'password']:
        return store.cast_value(value, str)

    if k == 'port':
        return store.cast_value(value, int)

    else:
        raise KeyError(key)


class TransmissionDownloader(plugin.Downloader):
    _STATE_MAP = {
        'download pending': models.Source.State.QUEUED,
        'downloading': models.Source.State.DOWNLOADING,
        'seeding': models.Source.State.SHARING,
        # other states need more logic
    }

    def __init__(self, app):
        super().__init__(app)

        self._logger = self.app.logger.getChild('transmission')
        self.app.settings.set_validator(settings_validator, ns=_SETTINGS_NS, )

        try:
            s = app.settings.get_tree(_SETTINGS_NS, {})
            self._api = transmissionrpc.Client(
                address=s.get('address', 'localhost'),
                port=s.get('port', 9091),
                user=s.get('user', None),
                password=s.get('password', None)
            )
            self._shield = {
                'urn:btih:' + x.hashString: x
                for x in self._api.get_torrents()}

        except transmissionrpc.error.TransmissionError as e:
            msg = "Unable to connect to transmission daemon: '{message}'"
            msg = msg.format(message=e.original.message)
            raise plugin.exc.BackendError(msg)

    def add(self, source, **kwargs):
        sha1_urn = downloads.calculate_urns(source.urn)[0]

        if sha1_urn in self._shield:
            self._logger.warning('Avoid duplicate')
            return self._shield[sha1_urn]

        try:
            ret = self._api.add_torrent(source.uri)
        except transmissionrpc.error.TransmissionError as e:
            raise plugin.exc.BackendError(e)

        self._shield[sha1_urn] = ret
        return ret

    def remove(self, item):
        self._shield = {
            urn: i for (urn, i) in self._shield.items() if i != item}
        return self._api.remove_torrent(item.id, delete_data=True)

    def list(self):
        return self._api.get_torrents()

    def get_state(self, tr_obj):
        # stopped status can mean:
        # - if progress is less that 100, source is paused
        # - if progress is 100, source can be paused or seeding completed
        #   isFinished attr can handle this
        if tr_obj.status == 'stopped':
            if tr_obj.progress < 100:
                return models.Source.State.PAUSED
            else:
                return models.Source.State.DONE

        state = tr_obj.status

        if state in self._STATE_MAP:
            return self._STATE_MAP[state]
        else:
            raise plugin.exc.NoMatchingState(state)

    def translate_item(self, tr_obj):
        urn = parse.parse_qs(
            parse.urlparse(tr_obj.magnetLink).query).get('xt')[0]
        urns = downloads.calculate_urns(urn)

        # Try to match urn in any form
        ret = None
        for u in urns:
            try:
                # Use like here for case-insensitive filter
                q = self.app.db.session.query(models.Source)
                q = q.filter(models.Source.urn.like(u))
                ret = q.one()
                break

            except orm.exc.MultipleResultsFound:
                msg = "Multiple results found for urn '{urn}'"
                msg = msg.format(urn=u)
                self._logger.error(msg)

                # There shouldn't be multiple results !!
                # Trying to do my best
                by_state = q.filter(models.Source.is_active is True)
                if by_state.count() == 1:
                    msg = ("Exception saved using state property but this is "
                           "a bug")
                    self._logger.error(msg)
                    ret = by_state.first()
                    break
                else:
                    msg = ("Unable to rescue invalid state. Multiple sources "
                           "found, fix this.")
                    self._logger.error(msg)

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
            # self._logger.error(msg)
            return None

        # Attach some fields to item
        for k in ('progress', ):
            try:
                setattr(ret, k, getattr(tr_obj, k))
            except:
                setattr(ret, k, None)

        return ret


__arroyo_extensions__ = [
    ('transmission', TransmissionDownloader)
]