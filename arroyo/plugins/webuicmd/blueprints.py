# -*- coding: utf-8 -*-

import itertools
import json

from flask import Blueprint, request, g
from flask.views import MethodView
from flask.ext.api import status
from flask.ext.api import exceptions


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
    def get(self):
        d = request.args.to_dict()

        try:
            limit = int(d.pop('limit', 10))
        except ValueError:
            limit = 10

        try:
            page = int(d.pop('page', 0))
        except ValueError:
            page = 0

        if not d:
            return []

        start = limit * page
        stop = start + limit

        res = g.app.selector.matches(selector.QuerySpec('foo', **d))
        res = sorted(res, key=lambda x: x.id)
        res = itertools.islice(res, start, stop)
        res = [json_filter(x.as_dict()) for x in res]

        return res


class SettingsView(MethodView):
    def get(self):
        return g.app.settings.get(None)

    def post(self):
        data = request.data
        g.app.settings.replace(data)
        return '', status.HTTP_204_NO_CONTENT

search = Blueprint('search', __name__)
search.add_url_rule(
    '/',
    view_func=SearchView.as_view('search_api'))

settings = Blueprint('settings', __name__)
settings.add_url_rule(
    '/',
    view_func=SettingsView.as_view('settings_api'))
