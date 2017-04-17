# -*- coding: utf-8 -*-


from arroyo import models


import contextlib
import sys

import tqdm
from appkit.db import sqlalchemyutils as sautils


@contextlib.contextmanager
def _mute_logger(logger):
    mute = 51
    prev = logger.getEffectiveLevel()
    logger.setLevel(mute)
    yield
    logger.setLevel(prev)


def _tqdm(*args, **kwargs):
    kwargs_ = dict(dynamic_ncols=True, disable=not sys.stderr.isatty())
    kwargs_.update(kwargs)

    return tqdm.tqdm(*args, **kwargs_)


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

    def delete(self, model, **kwargs):
        objs = self.get(model, **kwargs)
        self.session.delete(*objs)
        self.session.commit()

    def reset(self):
        for model in [models.Source, models.Movie, models.Episode]:
            for src in self.session.query(model):
                self.session.delete(src)
        self.session.commit()

    def update_all_states(self, state):
        for src in self.session.query(models.Source):
            src.state = state
        if state == models.State.NONE:
            self.session.query(models.Selection).delete()
        self.session.commit()

    def search(self, all_states=False, **kwargs):
        query = sautils.query_from_params(self.session, models.Source,
                                          **kwargs)
        if not all_states:
            query = query.filter(
                models.Source.state == models.State.NONE)

        return query

    def get_active(self):
        qs = self.session.query(models.Source)
        qs = qs.filter(
            ~models.Source.state.in_(
                (models.State.NONE, models.State.ARCHIVED)
            )
        )

        return qs

    def migrations(self):
        migrations = [
            ('01_normalize-entities',
             self._migration_normalize_entities),

            ('02_delete-entities-with-zero-sources',
             self._migration_delete_entities_with_zero_sources),

            ('03_migration_delete_false_selections',
             self._migration_delete_false_selections)
        ]

        for (name, fn) in migrations:
            fullname = 'core.db.migration.' + name
            if not self.app.variables.get(fullname, False):
                fn()
                self.app.variables.set(fullname, True)

    def _migration_normalize_entities(self):
        sess = self.app.db.session

        qs = sess.query(models.Source)
        count = qs.count()

        msg = "Rebuilding entities"
        pbar = _tqdm(total=count, desc=msg)

        with _mute_logger(self.app.mediainfo.logger):
            self.app.mediainfo.logger.setLevel(51)

            for (idx, src) in enumerate(qs):
                if src.entity:
                    prev_entity = src.entity
                    prev_selection = src.entity.selection
                else:
                    prev_entity = None
                    prev_selection = None

                self.app.mediainfo.process(src)

                # Update previous selection if entity has changed
                if prev_selection and prev_entity != src.entity:
                    prev_selection.entity = src.entity

                pbar.update()

            sess.commit()

    def _migration_delete_entities_with_zero_sources(self):
        sess = self.app.db.session

        # EntitySupport
        for model in [models.Episode, models.Movie]:
            qs = sess.query(model)
            count = qs.count()

            msg = "Delete '{model}'s without sources"
            msg = msg.format(model=model.__name__)
            pbar = _tqdm(total=count, desc=msg)

            deleted = 0
            for (idx, entity) in enumerate(qs):
                source_count = entity.sources.count()
                if source_count == 0:
                    sess.delete(entity)
                    deleted += 1

                pbar.update()

            # qs = sess.query(model).filter(~model.sources.any())
            # count = qs.count()
            # qs.delete(synchronize_session=False)
            msg = "Deleted {count} '{model}'s"
            msg = msg.format(count=count, model=model.__name__)
            print(msg)

        sess.commit()

    def _migration_delete_false_selections(self):
        sess = self.app.db.session

        source_ids = [x.id for x in sess.query(models.Source)]

        # EntitySupport
        for model in [models.Episode, models.Movie]:
            msg = "Deleting false {model} selections from database"
            msg = msg.format(model=model.__name__)
            print(msg)

            sess.query(model.SELECTION_MODEL).filter(
                ~model.SELECTION_MODEL.source_id.in_(source_ids)
            ).delete(synchronize_session='fetch')

            entity_ids = [x.id for x in sess.query(model)]
            for selection in sess.query(model.SELECTION_MODEL):
                if (selection.entity is None or
                        selection.entity.id not in entity_ids):
                    sess.delete(selection)

        sess.commit()
