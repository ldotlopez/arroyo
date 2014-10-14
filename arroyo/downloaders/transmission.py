# -*- coding: utf-8 -*-
# [SublimeLinter pep8-max-line-length:119]
# vim: set fileencoding=utf-8 :

from urllib import parse

from sqlalchemy.orm import exc

import transmissionrpc

from ldotcommons import logging

from arroyo import models, downloaders


_STATE_MAP = {
    'downloading': models.Source.State.DOWNLOADING,
    'seeding': models.Source.State.SHARING,
    # other states need more logic
}

_logger = logging.get_logger('downloader.transmission')


class Downloader:

    def __init__(self, session, *args, **kwargs):
        self._sess = session

        try:
            self._api = transmissionrpc.Client(**kwargs)
        except transmissionrpc.error.TransmissionError as e:
            raise downloaders.BackendError(e)

        self._shield = {
            'urn:btih:' + x.hashString: x for x in self._api.list().values()}

    def do_list(self):
        return self._api.get_torrents()

    def do_add(self, source, **kwargs):
        sha1_urn = downloaders.calculate_urns(source.id)[0]

        if sha1_urn in self._shield:
            _logger.warning('Avoid duplicate')
            return self._shield[sha1_urn]

        try:
            ret = self._api.add_torrent(source.uri)
        except transmissionrpc.error.TransmissionError as e:
            raise downloaders.BackendError(e)

        self._shield[sha1_urn] = ret
        return ret

    def do_remove(self, item):
        self._shield = {
            urn: i for (urn, i) in self._shield.items() if i != item}
        return self._api.remove_torrent(item.id, delete_data=True)

    def get_state(self, tr_obj):
        # stopped status can mean:
        # - if progress is less that 100, source is paused
        # - if progress is 100, source can be paused or seeding completed isFinished attr can handle this
        if tr_obj.status == 'stopped':
            if tr_obj.progress < 100:
                return models.Source.State.PAUSED
            else:
                return models.Source.State.DONE

        state = tr_obj.status

        if state in _STATE_MAP:
            return _STATE_MAP[state]
        else:
            raise downloaders.NoMatchingState(state)

    def translate_item(self, tr_obj):
        urn = parse.parse_qs(
            parse.urlparse(tr_obj.magnetLink).query).get('xt')[0]
        urns = downloaders.calculate_urns(urn)

        # Try to match urn in any form
        ret = None
        for u in urns:
            try:
                # Use like here for case-insensitive filter
                ret = self._sess.query(models.Source).filter(
                    models.Source.id.like(u)).one()
                break

            except exc.NoResultFound:
                pass

        if not ret:
            raise downloaders.NoMatchingItem(tr_obj.name)

        # Attach some fields to item
        for k in ('progress', ):
            try:
                setattr(ret, k, getattr(tr_obj, k))
            except:
                setattr(ret, k, None)

        return ret
