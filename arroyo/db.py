# -*- coding: utf-8 -*-


from arroyo import models


from appkit.db import sqlalchemyutils as sautils


class Db:
    def __init__(self, db_uri='sqlite:////:memory:'):

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
        # This is a _hack_ required by the webui plugin.
        if '?' in db_uri:
            db_uri += '&check_same_thread=False'
        else:
            db_uri += '?check_same_thread=False'

        self._sess = sautils.create_session(db_uri)

    @property
    def session(self):
        return self._sess

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
