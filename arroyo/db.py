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
        self.fixes()

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

    def delete(self, model, **kwargs):
        objs = self.get(model, **kwargs)
        self.session.delete(*objs)
        self.session.commit()

    def reset(self):
        for model in [models.Source, models.Movie, models.Episode]:
            for src in self._sess.query(model):
                self._sess.delete(src)
        self._sess.commit()

    def update_all_states(self, state):
        for src in self._sess.query(models.Source):
            src.state = state
        if state == models.State.NONE:
            self._sess.query(models.Selection).delete()
        self._sess.commit()

    def search(self, all_states=False, **kwargs):
        query = sautils.query_from_params(self._sess, models.Source, **kwargs)
        if not all_states:
            query = query.filter(
                models.Source.state == models.State.NONE)

        return query

    def get_active(self):
        query = self._sess.query(models.Source)
        query = query.filter(~models.Source.state.in_(
            (models.State.NONE, models.State.ARCHIVED)))

        return query

    def fixes(self):
        self._fix_entity_case()

    def _fix_entity_case(self):
        def _normalize(string):
            return string.lower()

        def _fix_entity_case(model, model_attr,
                             source_entity_attr,
                             selection_entity_attr):
            entity_map = {}
            entities = self.session.query(model)
            migration_count = entities.count()

            for (migration_idx, entity) in enumerate(entities):
                normalized = _normalize(getattr(entity, model_attr))

                if not migration_idx % 10:
                    print("Migrating {model} {count} of {total}".format(
                        model=model,
                        count=migration_idx,
                        total=migration_count))

                if normalized not in entity_map:
                    entity_map[normalized] = entity

                elif normalized != getattr(entity, model_attr):
                    for src in entity.sources:
                        setattr(
                            src,
                            source_entity_attr,
                            entity_map[normalized])

                    if entity.selection:
                        setattr(
                            entity.selection,
                            selection_entity_attr,
                            entity_map[normalized])

                    self.session.delete(entity)

        fix_value = self.get(models.Variable, key='db.fixes.entity-case')
        fix_value = 0 if fix_value is None else fix_value.value

        if fix_value > 1:
            msg = 'Invalid value for {variable}: {value}'
            msg = msg.format(variable='db.fixes.entity-case', value=fix_value)
            raise ValueError(msg)

        elif fix_value == 1:
            return

        else:
            _fix_entity_case(models.Episode, 'series', 'episode', 'episode')
            _fix_entity_case(models.Movie, 'title', 'movie', 'movie')

            var = models.Variable(key='db.fixes.entity-case', value=1)
            self.session.add(var)
            self.session.commit()
