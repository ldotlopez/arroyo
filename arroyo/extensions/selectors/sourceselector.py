from ldotcommons import utils
import sqlalchemy

from arroyo.app import app
from arroyo import (models)


@app.register('selector', 'source')
class SourceSelector:
    handles = []

    model = models.Source

    def __init__(self):
        for (colname, column) in self.model.__table__.columns.items():
            coltype = column.type

            if isinstance(coltype, sqlalchemy.String):
                self.handles.append(colname)
                self.handles.append(colname + '_like')
                self.handles.append(colname + '_regexp')

            if isinstance(coltype, sqlalchemy.Integer):
                self.handles.append(colname)
                self.handles.append(colname + '_min')
                self.handles.append(colname + '_max')

    def select(self, query=None, **params):
        if query is None:
            query = app.db.session.query(models.Source)

        for (k, v) in params.items():
            query = self.filter(query, k, v)

        return query

    def filter(self, query, key, value):
        if '_' in key:
            mod = key.split('_')[-1]
            key = '_'.join(key.split('_')[:-1])
        else:
            key = key
            mod = None

        attr = getattr(self.model, key, None)

        if mod == 'like':
            query = query.filter(attr.like(value))

        elif mod == 'regexp':
            query = query.filter(attr.op('regexp')(value))

        elif mod == 'min':
            value = utils.parse_size(value)
            query = query.filter(attr >= value)

        elif mod == 'max':
            value = utils.parse_size(value)
            query = query.filter(attr <= value)

        else:
            query = query.filter(attr == value)

        return query