# -*- coding: utf-8 -*-

from arroyo import plugin
from arroyo import models

import json
from sqlalchemy import and_
import tvdb_api
from ldotcommons import utils
from ldotcommons.sqlalchemy import Base
from sqlalchemy import schema, Column, Integer, String, ForeignKey


class TVDBInfo(Base):
    __tablename__ = 'tvdbinfo'

    id = Column(
        String,
        primary_key=True)

    timestamp = Column(
        Integer,
        nullable=False,
        default=utils.now_timestamp)

    data = Column(
        String,
        name='value',
        nullable=False)


class TVDB:
    def __init__(self, app):
        # Create model
        models.Base.metadata.create_all(app.db.session.connection())
        self.app = app
        self.api = tvdb_api.Tvdb()

    def series_id(self, ep):
        id_ = ep.series
        if ep.year:
            id_ += '(' + ep.year + ')'

        return id_

    def season_id(self, ep):
        return ep.season or '-'

    def episode_id(self, ep):
        return ep.episode or '-'

    def load_series_info(self, ep):

        now = utils.now_timestamp()
        cutoff = now - 60*60*24*7

        id_ = 'series.{}'.format(
            self.series_id(ep).replace('.', '-')
        )

        info = self.app.db.session.query(
            TVDBInfo
        ).filter(and_(
            TVDBInfo.id == id_,
            TVDBInfo.timestamp >= cutoff
        )).one_or_none()

        if info is None:
            return

        return json.loads(info.data)

    def save_series_info(self, ep, info):
        id_ = 'series.{}'.format(
            self.series_id(ep).replace('.', '-')
        )
        obj = TVDBInfo(id=id_, data=json.dumps(info))
        self.app.db.session.add(obj)

    def process(self, *src_ids):
        srcs = self.app.db.session.query(
            plugin.models.Source
        ).filter(and_(
            plugin.models.Source.episode != None,  # nopep8
            plugin.models.Source.id.in_(src_ids)
        ))

        eps = set(map(lambda src: src.episode, srcs))
        sess = self.app.db.session
        for ep in eps:
            # Check series info
            series_info = self.load_series_info(ep)
            if not series_info:
                series_info = self.api[self.series_id(ep)]
                self.save_series_info(ep, series_info.data)

        sess.commit()


class TVDBCommand(plugin.Command):
    help = 'tvdb'
    arguments = (
        plugin.cliargument(
            '-i', dest='item', required=True, type=int
        ),
    )

    def run(self, arguments):
        tvdb = TVDB(self.app)
        tvdb.process(arguments.item)

__arroyo_extensions__ = [
    TVDBCommand
]
