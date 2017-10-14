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


from arroyo import models


from appkit.db import sqlalchemyutils as sautils
from sqlalchemy import orm
from sqlalchemy.engine import reflection
from sqlalchemy.orm import util


class Db:
    def __init__(self, app, db_uri='sqlite:////:memory:'):

        # sqlalchemy scoped session mode

        # engine = sqlalchemy.create_engine(db_uri)
        # session_factory = sqlalchemy.orm.sessionmaker(bind=engine)
        # self._sess = sqlalchemy.orm.scoped_session(session_factory)()
        # models.Base.metadata.create_all(engine)

        # sqlalchemy session maker mode

        # engine = sqlalchemy.create_engine(db_uri)
        # sessmaker = orm.sessionmaker()
        # sessmaker.configure(bind=engine)
        # models.Base.metadata.create_all(engine)
        # self._sess = sessmaker()

        # Add check_same_thread=False to db_uri.
        # FIXME: This is a _hack_ required by the webui plugin.
        if '?' in db_uri:
            db_uri += '&check_same_thread=False'
        else:
            db_uri += '?check_same_thread=False'

        self.app = app
        self.session = sautils.create_session(db_uri)

    def install_model(self, model):
        model.metadata.create_all(self.session.connection())

    def get(self, model, **kwargs):
        query = self.session.query(model).filter_by(**kwargs)
        count = query.count()

        if count == 0:
            return None
        if count == 1:
            return query.one()
        else:
            return query.all()

    def get_or_create(self, model, **kwargs):
        o = self.get(model, **kwargs)

        if o:
            return o, False
        else:
            return model(**kwargs), True

    def reconciliate(self, obj_or_data, model=None):
        def _is_sa_mapped_cls(cls):
            try:
                util.class_mapper(cls)
                return True
            except:
                return False

        def _is_sa_mapped_obj(obj):
            try:
                util.object_mapper(obj)
                return True
            except:
                return False

        def _extract_from_model_instance(keys):
            return {k: getattr(obj_or_data, k) for k in keys}

        def _extract_from_dict(key):
            return {k: obj_or_data[k] for k in keys}

        # Check arguments.
        if _is_sa_mapped_obj(obj_or_data):
            tablename = obj_or_data.__tablename__
            model = obj_or_data.__class__
            extract_fn = _extract_from_model_instance

        elif isinstance(obj_or_data, dict):
            if not _is_sa_mapped_cls(model):
                raise TypeError('model missing for dicts')

            tablename = model.__tablename__
            extract_fn = _extract_from_dict
        else:
            raise TypeError('obj_or_data neither model instance or dict')

        ins = reflection.Inspector(self.session.get_bind())
        for uniq in ins.get_unique_constraints(tablename):
            keys = uniq['column_names']

            try:
                data = extract_fn(keys)
            except (KeyError, AttributeError):
                pass

            try:
                return self.session.query(model).filter_by(**data).one()
            except orm.exc.NoResultFound:
                continue

        if isinstance(obj_or_data, dict):
            return model(**obj_or_data)
        else:
            return obj_or_data

    def reconciliate_all(self, objs_or_datas, model=None):
        return [self.reconciliate(x, model) for x in objs_or_datas]

    def delete(self, model, **kwargs):
        objs = self.get(model, **kwargs)
        self.session.delete(*objs)
        self.session.commit()

    def reset(self):
        for model in [models.Source, models.Movie, models.Episode]:
            for src in self.session.query(model):
                self.session.delete(src)
        self.session.commit()

    def search(self, all_states=False, **kwargs):
        query = sautils.query_from_params(self.session, models.Source,
                                          **kwargs)
        if not all_states:
            query = query.filter(
                models.Source.state == models.State.NONE)

        return query
