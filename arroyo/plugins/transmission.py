# -*- coding: utf-8 -*-


from arroyo import plugin
from arroyo.plugin.tools import downloads


from urllib import parse


from appkit import store
from sqlalchemy import orm
import transmissionrpc


models = plugin.models


class TransmissionDownloader(plugin.Downloader):
    __extension_name__ = 'transmission'

    _SETTINGS_NS = 'plugin.transmission'

    _STATE_MAP = {
        'download pending': models.Source.State.QUEUED,
        'downloading': models.Source.State.DOWNLOADING,
        'seeding': models.Source.State.SHARING,
        # other states need more logic
    }

    def __init__(self, app):
        super().__init__(app)

        self._logger = self.app.logger.getChild('transmission')
        self.app.settings.add_validator(self.settings_validator)

        try:
            s = app.settings.get(self._SETTINGS_NS, default={})
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
                self._logger.critical(msg)
                raise

                # # This code was used to workaroung this exception.
                # # Delete it since its better to fix this bug!
                # # There shouldn't be multiple results !!
                # # Trying to do my best
                # by_state = q.filter(models.Source.is_active is True)
                # if by_state.count() == 1:
                #     msg = ("Exception saved using state property but this "
                #            "is a bug")
                #     self._logger.error(msg)
                #     ret = by_state.first()
                #     break
                # else:
                #     msg = ("Unable to rescue invalid state. Multiple "
                #            "sources found, fix this.")
                #     self._logger.error(msg)

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

    @staticmethod
    def settings_validator(key, value):
        if not key.startswith('plugin.transmission'):
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
