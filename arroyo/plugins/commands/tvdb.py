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


from arroyo import pluginlib


import json


import tvdb_api
from appkit import utils
from appkit.db import sqlalchemyutils as sautils
from sqlalchemy import (
    Column,
    Integer,
    String,
    and_
)


models = pluginlib.models


class TVDBInfo(sautils.Base):
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
    def __init__(self, db):
        # Create model
        # FIXME: define a method to install models into db
        models.Base.metadata.create_all(db.session.connection())
        self.db = db
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

        info = self.db.session.query(
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
        self.db.session.add(obj)

    def process(self, *src_ids):
        srcs = self.db.session.query(
            models.Source
        ).filter(and_(
            pluginlib.Source.episode != None,  # nopep8
            pluginlib.Source.id.in_(src_ids)
        ))

        eps = set(map(lambda src: src.episode, srcs))
        sess = self.db.session
        for ep in eps:
            # Check series info
            series_info = self.load_series_info(ep)
            if not series_info:
                series_info = self.api[self.series_id(ep)]
                self.save_series_info(ep, series_info.data)

        sess.commit()


class TVDBCommand(pluginlib.Command):
    HELP = 'tvdb'
    ARGUMENTS = (
        pluginlib.cliargument(
            '-i', dest='item', required=True, type=int
        ),
    )

    def run(self, app, arguments):
        db = app.db

        tvdb = TVDB(db)
        tvdb.process(arguments.item)

__arroyo_extensions__ = [
    TVDBCommand
]
