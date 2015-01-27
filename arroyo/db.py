from sqlalchemy import orm
from ldotcommons import (sqlalchemy as ldotsa, utils)

import arroyo.exc
from arroyo import models


class Db:
    def __init__(self, db_uri='sqlite:////:memory:'):
        # engine = sqlalchemy.create_engine(db_uri)
        # sessmaker = orm.sessionmaker()
        # sessmaker.configure(bind=engine)
        # models.Base.metadata.create_all(engine)
        # self._sess = sessmaker()
        # FIXME: ldotcommons.sqlalchemy.create_session it's not totally safe,
        # review this.
        self._sess = ldotsa.create_session(db_uri)

    @property
    def session(self):
        return self._sess

    @session.setter
    def session(self, value):
        raise arroyo.exc.ReadOnlyProperty()

    def get(self, model, **kwargs):
        query = self.session.query(model).filter_by(**kwargs)

        # FIXME: Handle multiple rows found?
        try:
            return query.one()
        except orm.exc.NoResultFound:
            return None

    def get_or_create(self, model, **kwargs):
        obj = self.get(model, **kwargs)
        if not obj:
            return model(**kwargs), True
        else:
            return obj, False

    def reset(self):
        for model in [models.Source, models.Movie, models.Episode]:
            for src in self._sess.query(model):
                self._sess.delete(src)
        self._sess.commit()

    def update_all_states(self, state):
        for src in self._sess.query(models.Source):
            src.state = state
        if state == models.Source.State.NONE:
            self._sess.query(models.Selection).delete()
        self._sess.commit()

    def shell(self):
        print("[!!] Database connection in 'sess' {}".format(self._sess))
        print("[!!] If you make any changes remember to call sess.commit()")
        sess = self._sess  # nopep8
        utils.get_debugger().set_trace()

    def search(self, all_states=False, **kwargs):
        query = ldotsa.query_from_params(self._sess, models.Source, **kwargs)
        if not all_states:
            query = query.filter(
                models.Source.state == models.Source.State.NONE)

        return query

    def get_active(self):
        query = self._sess.query(models.Source)
        query = query.filter(~models.Source.state.in_(
            (models.Source.State.NONE, models.Source.State.ARCHIVED)))

        return query
