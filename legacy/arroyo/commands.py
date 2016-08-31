# -*- coding: utf-8 -*-
# [SublimeLinter pep8-max-line-length:119]
# vim: set fileencoding=utf-8 :

raise Exception('Deprecated file')

import re

import guessit
from sqlalchemy.orm import exc

from flask import request, url_for, redirect
from flask.ext.api import FlaskAPI, status

from appkit import logging
from appkit import sqlalchemy as ldotsa
from appkit import utils

from arroyo import Arroyo, ArgumentError
from arroyo import models


_logger = logging.get_logger('arroyo.commands')


#
# Mediainfo subcommand
#
# def mediainfo(**opts):
#    dburi = opts.pop('db_uri')
#    if not dburi:
#        raise ArgumentError('database uri is required')
#
#    conn = ldotsa.create_session(dburi)
#
#    for source in conn.query(db.Source).all():
#        _logger.info("Looking for metainfo for '{}'".format(source))
#        _mediainfo_link(conn, source)
#
#    conn.commit()
#
#
# def _mediainfo_link(sess, source):
#    info = guessit.guess_file_info(source.name)
#
# Fix language
#    source_type = info.pop('type')
#    if source.type in (None, 'unknow'):
#        source.type = source_type
#
#    if 'language' in info:
#        info['language'] = [x.english_name for x in info['language']]
#
# Some fixes for info
#    fixes = (('movie', ('title',), '.avi'),
#             ('episode', ('series', 'season', 'episodeNumber'), '.mp4'))
#
#    for (type_, fields, ext) in fixes:
#        if source_type == type_ and fields[0] not in info:
#            info2 = guessit.guess_file_info(source.name + ext)
#            for field in fields:
#                try:
#                    info[field] = info2[field]
#                except KeyError:
#                    pass
#
#    if source_type == 'movie':
#        source.episode = None
#        try:
#            arguments = {'title': info['title']}
#        except KeyError:
# FIXME: Print some warning or raise exception
#            return
#
#        arguments['year'] = info.get('year', None)
#
#        movie = None
#        try:
#            movie = sess.query(db.Movie).filter_by(**arguments).one()
#        except exc.NoResultFound:
#            pass
#
#        if not movie:
#            movie = db.Movie(**arguments)
#
#        movie.sources.append(source)
#
#    if source_type == 'episode':
#        try:
#            arguments = {
#                'series': info['series'],
#                'season': info.get('season', -1),
#                'episode_number': info['episodeNumber']
#            }
#
#        except KeyError:
# FIXME: Print some warning or raise exception
#            return
#
#        arguments['year'] = info.get('year', None)
#
#        episode = None
#        try:
#            episode = sess.query(db.Episode).filter_by(**arguments).one()
#        except exc.NoResultFound:
#            pass
#
#        if not episode:
#            episode = db.Episode(**arguments)
#
#        episode.sources.append(source)
#        source.movie = None
#
# Webui
#
def generic_repr(x):
    return {k: v for (k, v) in x}

source_repr = generic_repr
series_repr = generic_repr


def movie_repr(movie):
    return {
        'title': movie.title,
        'year': movie.year
    }


class WebUI(FlaskAPI):

    def __init__(self, session, downloader):
        super(WebUI, self).__init__(__name__)
        #self.sess = session
        #self.downloader = downloader

        self.route('/')(self.main)

        self.route('/introspect/')(self.introspect)

        self.route('/browse/')(self.browse)
        self.route('/browse/<string:category>/')(self.browse)
        self.route('/browse/movies/')(self.list_movies)
        self.route('/browse/episodes/')(self.list_series)
        self.route('/browse/series/<string:series>/')(self.list_series)
        self.route('/browse/series/<string:series>/seasons/')(self.list_seasons)
        self.route('/browse/series/<string:series>/seasons/<int:season>')(self.list_episodes)

        self.route('/search/')(self.search)

        self.route('/downloads/', methods=['GET'])(self.downloads_list)
        self.route('/downloads/', methods=['POST'])(self.downloads_add)
        self.route('/downloads/<string:id_>', methods=['GET'])(self.downloads_detail)
        self.route('/downloads/<string:id_>', methods=['DELETE'])(self.downloads_remove)

    @staticmethod
    def is_safe_type(t):
        return re.search(r'^[a-z]+(\-[a-z]+)?$', t) is not None

    @staticmethod
    def is_safe_language(l):
        return re.search(r'^[a-z]{2}(\-[a-z]{2,3})*$', l) is not None

    def main(self):
        return redirect(url_for('static', filename='index.html'))

    def introspect(self):
        return {
            'types': [x[0] for x in self.sess.query(db.Source.type).distinct().all() if x[0] is not None],
            'languages': [x[0] for x in self.sess.query(db.Source.language).distinct().all() if x[0] is not None]
        }

    def browse(self, category=None):
        return [category]

    def list_movies(self):
        return []
        #page = request.args.get('page', 0)
        # return [movie_repr(movie) for movie in self.sess.query(db.Movie).all()]

    def list_series(self, series=None):
        return []
        #q = self.sess.query(db.Episode.series, db.Episode.year).group_by(db.Episode.series, db.Episode.year)
        # return [{'series': series, 'year': year} for (series, year) in q.all()]

    def list_seasons(self, series):
        return []

    def list_episodes(self, series, season):
        return []

    def search(self):
        # name search
        try:
            q = request.args.get('q', '')
        except IndexError:
            q = ''

        # All states parameter
        all_states = 'all_states' in request.args

        # Get types and filter
        types = [x for x in request.args.getlist('type') if WebUI.is_safe_type(x)]
        languages = [x for x in request.args.getlist('language') if WebUI.is_safe_language(x)]

        if len(q) < 3:
            return {'error': 'query too vague'}, status.HTTP_400_BAD_REQUEST

        replacements = (
            (' ', '_'),
            ('*', '%'),
            ('.', '_'))
        for (i, o) in replacements:
            q = q.replace(i, o)
        q = '%' + q + '%'

        ret = ldotsa.query_from_params(self.sess, db.Source, name_like=q)

        if types:
            ret = ret.filter(db.Source.type.in_(types))

        if languages:
            ret = ret.filter(db.Source.language.in_(languages))

        return [source_repr(source) for source in ret.all()]

    def downloads_list(self):
        dler_objs = self.downloader.list()
        db_objs = self.sess.query(db.Source).filter(
            ~db.Source.state.in_((db.Source.State.NONE, db.Source.State.ARCHIVED)))

        missing_objs = [x for x in db_objs if x not in dler_objs]

        for obj in missing_objs:
            # Archive object
            obj.state = db.Source.State.ARCHIVED
            _logger.warning('State change {}'.format(obj))

        self.sess.commit()

        return [source_repr(x) for x in dler_objs]

    def downloads_add(self):
        try:
            id_ = request.data['id']
            source = self.sess.query(db.Source).filter(db.Source.id == id_).one()
            if self.downloader.add(source):
                return {}, status.HTTP_204_NO_CONTENT
            else:
                return {'error': 'unknow error'}, status.HTTP_400_BAD_REQUEST

        except (KeyError, exc.NoResultFound):
            return {'error': 'Invalid source'}, status.HTTP_404_NOT_FOUND

    def downloads_detail(self, id_):
        try:
            source = self.sess.query(db.Source).filter(db.Source.id == id_).one()
            return source_repr(self.downloader.info(source))

        except (KeyError, exc.NoResultFound):
            return {'error': 'Invalid source'}, status.HTTP_404_NOT_FOUND

    def downloads_remove(self, id_):
        try:
            source = self.sess.query(db.Source).filter(db.Source.id == id_).one()
            self.downloader.remove(source)
            return {}

        except exc.NoResultFound:
            return {'error': 'Invalid source'}, status.HTTP_404_NOT_FOUND


def webui(db_uri, downloader_name):
    from . import Arroyo
    core = Arroyo(db_uri=db_uri, downloader_name=downloader_name)
    WebUI2(core).run(host='0.0.0.0', debug=True)

    #db_conn = ldotsa.create_session(db_uri)

    #downloader_mod = importlib.import_module('arroyo.downloaders.'+downloader_name)
    #downloader = getattr(downloader_mod, 'Downloader')(session=db_conn)
    #
    #webui = WebUI(session=db_conn, downloader=downloader)
    #webui.run(host='0.0.0.0', debug=True)
