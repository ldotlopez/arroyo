import re

from flask import Blueprint, request, g
from flask.views import MethodView
from flask.ext.api import status
from flask.ext.api import exceptions

from arroyo import models
from itertools import chain


class TransformError(Exception):
    def __init__(self, param, detail=""):
        self.param = param
        self.detail = detail
        super(Exception, self).__init__()


def source_repr(x):
    return x.as_dict()


class SearchView(MethodView):
    def get(self, offset=None, limit=None):
        q = request.args.get('q', None)
        if not q:
            return []

        res = [
            g.app.selector.get_selector({
                'selector': 'episode',
                'series': q
            }).list(),
            g.app.selector.get_selector({
                'selector': 'movie',
                'title': q
            }).list(),
        ]

        return [
            source_repr(x) for x in
            chain.from_iterable(res)
        ]


class EpisodeView(MethodView):
    def get(self):
        pass

search_view = SearchView.as_view('search_api')

search = Blueprint('search', __name__)
search.add_url_rule(
    '',
    view_func=search_view,
    methods=['GET'])

# search.add_url_rule(
#     '',
#     view_func=search_view,
#     methods=['GET'],
#     defaults={'search_str': None})
# search.add_url_rule(
#     '/str:search_str',
#     view_func=search_view,
#     methods=['GET'])


# class CRUDView(MethodView):
#     Model = None

#     def get_raw(self, obj_id=None):
#         if obj_id is None:
#             return self.Model.query.order_by(self.Model.id.desc())
#         else:
#             return self.Model.query.get_or_404(obj_id)

#     def get(self, obj_id=None, offset=None, limit=None):
#         limit = 10 if limit is None else limit
#         offset = 0 if offset is None else offset

#         if obj_id is None:
#             return [self.serialize(x)
#                     for x in self.paginate(self.get_raw(), offset, limit)]
#         else:
#             return self.serialize(self.get_raw(obj_id))

#     def post(self):
#         obj = self.Model()

#         try:
#             params = self.transform_data(**request.data)
#         except TransformError as e:
#             raise exceptions.ParseError(
#                 "Invalid parameter: {}".format(e.param))

#         try:
#             obj.update(**params)
#         except ModelException as e:
#             raise exceptions.ParseError(str(e))

#         db.session.add(obj)
#         try:
#             db.session.commit()
#             return self.serialize(obj), status.HTTP_201_CREATED

#         except exc.IntegrityError as e:
#             db.session.rollback()
#             raise exceptions.ParseError("IntegrityError {error}".format(
#                 error=str(e)))

#     def put(self, obj_id):
#         obj = self.get_raw(obj_id)
#         try:
#             params = self.transform_data(**request.data)
#         except TransformError as e:
#             raise exceptions.ParseError("Invalid parameter: {}".format(
#                 e.param))

#         try:
#             obj.update(**params)
#         except ModelException as e:
#             raise exceptions.ParseError(str(e))

#         try:
#             db.session.commit()
#             return self.serialize(obj)

#         except exc.IntegrityError as e:
#             db.session.rollback()
#             raise exceptions.ParseError("IntegrityError {error}".format(
#                 error=str(e)))

#     def delete(self, obj_id):
#         obj = self.get_raw(obj_id)
#         db.session.delete(obj)
#         try:
#             db.session.commit()
#         except exc.IntegrityError as e:
#             raise exceptions.ParseError("IntegrityError {error}".format(
#                 error=str(e)))

#         return '', status.HTTP_204_NO_CONTENT

#     def paginate(self, query_set, offset=None, limit=None):
#         if offset is None:
#             offset = 0

#         if limit is None:
#             limit = 10

#         query_set = query_set.order_by(self.Model.id.desc())
#         return query_set[offset*limit:(offset+1)*limit]

#     def serialize(self, obj):
#         raise NotImplemented()

#     def transform_data(self, **data):
#         raise NotImplemented()


# class PersonView(CRUDView):
#     Model = Person

#     def get(self, obj_id):
#         if obj_id:
#             return super(PersonView, self).get(obj_id)

#         q = request.args.get('q')

#         try:
#             offset = int(request.args.get('offset'))
#         except (TypeError, ValueError):
#             offset = 0

#         if not q:
#             query_set = self.Model.query
#         else:
#             query_set = self.Model.query.filter(or_(
#                 Person.name.like('%{}%'.format(q)),
#                 Person.surname.like('%{}%'.format(q)),
#                 Person.email.like('%{}%'.format(q))
#             ))

#         return [self.serialize(x)
#                 for x in self.paginate(query_set, offset=offset)]

#     def serialize(self, obj):
#         ret = obj.as_dict()

#         ret['activities'] = [x.as_dict() for x in obj.activities]
#         for (idx, activity) in enumerate(ret['activities']):
#             del(ret['activities'][idx]['person'])

#         if obj.section:
#             ret['section'] = {
#                 'id': obj.section.id,
#                 'name': obj.section.name
#             }
#         else:
#             ret['section'] = None

#         return ret

#     def transform_data(self, **data):
#         # Filter out some params
#         for x in 'id', 'activities':
#             if x in data:
#                 raise TransformError(x, detail="not allowed")

#         # Section must be transformed
#         if 'section' in data:
#             try:
#                 section_id = int(data.pop('section'))
#             except (ValueError, TypeError):
#                 raise TransformError(
#                     'section',
#                     detail="invalid value")

#             try:
#                 data['section'] = Section.query.filter(
#                     Section.id == section_id).one()
#             except orm.exc.NoResultFound:
#                 raise TransformError(
#                     'section',
#                     detail="id {} not found".format(section_id))

#         # Simplify phone
#         if 'phone' in data:
#             data['phone'] = re.sub(r'[^\d]', '', data['phone'] or "")

#         # Nullables
#         nullables = ['name', 'surname', 'email', 'phone', 'notes']
#         nullables = filter(lambda x: x in data, nullables)
#         nullables = filter(lambda x: data[x] is not None, nullables)
#         nullables = filter(lambda x: re.sub(r'\s+', '', data[x]) == "",
#                            nullables)
#         for n in nullables:
#             data[n] = None

#         return data


# class SectionView(CRUDView):
#     Model = Section

#     # Redefine get_raw to get order_by in asc mode
#     def get_raw(self, obj_id=None):
#         if obj_id is None:
#             return self.Model.query.order_by(self.Model.name.asc())
#         else:
#             return self.Model.query.get_or_404(obj_id)

#     def serialize(self, obj):
#         return {'id': obj.id, 'name': obj.name}

#     # Disable pagination
#     def paginate(self, query_set, offset=None, limit=None):
#         return query_set


# class ActivityView(CRUDView):
#     Model = Activity

#     def get(self, obj_id):
#         if obj_id:
#             return super(ActivityView, self).get(obj_id)

#         q = request.args.get('q')

#         try:
#             person_id = request.args.get('person_id')
#         except (TypeError, ValueError):
#             person_id = None

#         try:
#             offset = int(request.args.get('offset'))
#         except (TypeError, ValueError):
#             offset = 0

#         query_set = self.Model.query

#         if q:
#             q = re.sub('[^a-zA-Z\s0-9\-\_]', '%', q)
#             query_set = query_set.filter(or_(
#                 self.Model.description.like('%{}%'.format(q)),
#                 Person.name.like('%{}%'.format(q)),
#                 Person.surname.like('%{}%'.format(q))
#                 ))

#         query_set = query_set.order_by(self.Model.stamp.desc())

#         if person_id:
#             query_set = query_set.filter(
#                 self.Model.person_id == person_id)

#         return [self.serialize(x)
#                 for x in self.paginate(query_set, offset=offset)]

#     def serialize(self, obj):
#         ret = obj.as_dict()
#         ret['person'] = obj.person.as_dict()
#         del(ret['person']['activities'])

#         return ret

#     def transform_data(self, **data):
#         # Unallowed keys
#         if 'id' in data:
#             raise TransformError('id', detail='not allowed')

#         # Transform person
#         if 'person' in data:
#             try:
#                 person_id = int(data['person'])
#             except ValueError:
#                 raise TransformError('person', detail="invalid value")

#             try:
#                 data['person'] = Person.query.filter(
#                     Person.id == person_id).one()
#             except orm.exc.NoResultFound:
#                 raise TransformError(
#                     'person',
#                     detail="ID {} not found".format(person_id))

#         if 'duration' in data:
#             try:
#                 data['duration'] = int(data['duration'])
#             except (ValueError, TypeError):
#                 raise TransformError('duration', detail="invalid value")

#         return data


# #
# # Sections API
# #
# sections_view = SectionView.as_view('section_api')
# sections = Blueprint('sections', __name__)
# sections.add_url_rule(
#     '',
#     view_func=sections_view,
#     methods=['GET'])
# sections.add_url_rule(
#     '/<int:obj_id>',
#     view_func=sections_view,
#     methods=['GET'])

# #
# # search API
# #
# search_view = PersonView.as_view('person_api')
# search = Blueprint('search', __name__)
# search.add_url_rule(
#     '',
#     view_func=search_view,
#     methods=['GET'],
#     defaults={'obj_id': None})
# search.add_url_rule(
#     '',
#     view_func=search_view,
#     methods=['POST'])
# search.add_url_rule(
#     '/<int:obj_id>',
#     view_func=search_view,
#     methods=['GET', 'PUT', 'DELETE'])

# #
# # Activities API
# #
# activities = Blueprint('activities', __name__)
# activities_view = ActivityView.as_view('activiy_api')
# activities.add_url_rule(
#     '',
#     view_func=activities_view,
#     methods=['GET'],
#     defaults={'obj_id': None})
# activities.add_url_rule(
#     '',
#     view_func=activities_view,
#     methods=['POST'])
# activities.add_url_rule(
#     '/<int:obj_id>',
#     view_func=activities_view,
#     methods=['GET', 'PUT', 'DELETE'])
