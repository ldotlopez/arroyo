# -*- coding: utf-8 -*-

import itertools


from flask import Blueprint, request, g
from flask.views import MethodView
# from flask.ext.api import status
# from flask.ext.api import exceptions


from arroyo import selector


def json_filter(d):
    valid_types = (bool, int, float, str, list, dict, set)

    ret = {}

    for (k, v) in d.items():
        if isinstance(v, valid_types):
            ret[k] = v

        if isinstance(v, object):
            try:
                ret[k] = json_filter(v.as_dict())
            except (AttributeError):
                pass

    return ret


class SearchView(MethodView):
    def get(self, offset=0, limit=100):
        d = request.args.to_dict()
        if not d:
            return []

        qspec = selector.QuerySpec('foo', **request.args.to_dict())

        res = g.app.selector.select(qspec)
        res = itertools.islice(res, offset, offset + limit)
        res = [json_filter(x.as_dict()) for x in res]

        return res

search = Blueprint('search', __name__)
search.add_url_rule(
    '',
    view_func=SearchView.as_view('search_api'),
    methods=['GET'])
