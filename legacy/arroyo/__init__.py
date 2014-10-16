# -*- coding: utf-8 -*-
# [SublimeLinter pep8-max-line-length:119]
# vim: set fileencoding=utf-8 :

import importlib
import re
from urllib import parse

import blinker

from flask import request, url_for, redirect
from flask.ext.api import FlaskAPI, status

from sqlalchemy.orm import exc

from ldotcommons import fetchers
from ldotcommons import logging
from ldotcommons import sqlalchemy as ldotsa
from ldotcommons import utils

from arroyo import models, downloaders, importers


_UA = 'Mozilla/5.0 (X11; Linux x86) Home software (KHTML, like Gecko)'
_logger = logging.get_logger('arroyo')

SIGNALS = {k: blinker.signal(k) for k in (
    'source-add',
    'source-update',
    'source-state-change'
)}


class ArgumentError(Exception):
    def __init__(self, msg, *args, tip=True, **kwargs):
        if not msg.endswith('.'):
            msg += "."
        msg += " Try -h/--help switch"
        super(ArgumentError, self).__init__(msg, *args, **kwargs)


class DisabledService(Exception):
    pass


class SourceNotFound(Exception):
    pass


class ReadOnlyProperty(Exception):
    pass


class Arroyo:

    def __init__(self, db_uri, user_agent=_UA, **opts):
        self._sess = ldotsa.create_session(db_uri)
        self._ua = user_agent
        self.options = opts

        self._downloader = ArroyoDownloader(
            self) if opts.get('downloader_name', None) else None

        self._webui = WebUI(self) if opts.get('webui', False) else None

    @property
    def downloader(self):
        if self._downloader is None:
            raise DisabledService('downloader')
        return self._downloader

    @downloader.setter
    def downloader(self, x):
        raise ReadOnlyProperty()

    @property
    def webui(self):
        if self._webui is None:
            raise DisabledService('downloader')
        return self._webui

    @webui.setter
    def webui(self, x):
        if x:
            self._webui = WebUI(self)
        else:
            self._webui = None

    @property
    def session(self):
        return self._sess

    @session.setter
    def session(self, x):
        raise ReadOnlyProperty()

    def analize(self,
                analizer_name, seed_url=None, iterations=1,
                type_=None, language=None):
        """
        Analize an origin merging discovered sources into Database
        """
        # print("Analizeing", analizer_name, seed_url)

        #
        # Usual argument checking
        #
        if analizer_name is None:
            raise ArgumentError('analizer name is required')

        if not isinstance(seed_url, (str, type(None))):
            raise ArgumentError('seed_url must be an string or None')

        if not isinstance(iterations, int) or iterations < 1:
            raise ArgumentError('iterations must be an integer greater than 1')

        if not isinstance(type_, (str, type(None))):
            raise ArgumentError('type must be an string or None')

        if not isinstance(language, (str, type(None))):
            raise ArgumentError('languge must be an string or None')

        analizer_mod = importlib.import_module(
            'arroyo.importers.' + analizer_name)

        iterations = max(1, iterations)

        #
        # Prepare some objects before looping over generated urls
        #
        url_generator = analizer_mod.url_generator(seed_url)
        fetcher = fetchers.UrllibFetcher(
            cache=True, cache_delta=60 * 20, headers={'User-Agent': self._ua})
        overrides = {
            'type': type_,
            'language': language,
            'provider': analizer_mod.__name__.split('.')[-1]
        }
        overrides = {k: v for (k, v) in overrides.items() if v is not None}

        sources = []

        #
        # Start processing
        #
        for iter_ in range(0, iterations):
            # Get an URL from generator
            url = next(url_generator)

            msg = "{analizer_name}: iteration {iteration}/{iterations}: {url}"
            _logger.debug(msg.format(
                analizer_name=analizer_name,
                iteration=(iter_ + 1),
                iterations=(iterations),
                url=url))

            # Fetch its contents
            buffer = fetcher.fetch(url)

            # Pass buffer over analizer funcion and fix some fields
            try:
                srcs = analizer_mod.process(buffer)
            except importers.ProcessException:
                msg = 'Error processing {url} with {analizer_name}, skipping'
                _logger.warning(msg.format(
                    url=url, analizer_name=analizer_name))
                continue

            for src in srcs:
                src['id'] = parse.parse_qs(
                    parse.urlparse(src['uri']).query)['xt'][-1]
                src.update(overrides)

            sources += srcs

        ret = {'source-update': [], 'source-add': []}

        # In some cases there are no sources
        if not sources:
            return ret

        # Get existing sources before doing any insert or update
        sources = {x['id']: x for x in sources}
        query = self._sess.query(models.Source).filter(
            models.Source.id.in_(sources.keys()))
        existing = {x.id: x for x in query.all()}

        for (id_, src) in sources.items():
            obj = existing.get(id_, None)

            if not obj:
                obj = models.Source(**src)
                self._sess.add(obj)
                ret['source-add'].append(obj)
                SIGNALS['source-add'].send(source=obj)
            else:
                for key in src:
                    setattr(obj, key, src[key])
                ret['source-update'].append(obj)
                SIGNALS['source-update'].send(source=obj)

        self._sess.commit()
        return ret

    def sync(self):
        ret = {'sources-state-change': []}

        downloads = set(self.downloader.list())
        actives = set(self.get_active())

        for source in actives - downloads:
            source.state = models.Source.State.ARCHIVED
            ret['sources-state-change'].append(source)
            SIGNALS['source-state-change'].send(source=source)

        self._sess.commit()
        return ret

    def reset(self):
        for model in [models.Source, models.Movie, models.Episode]:
            for src in self._sess.query(model):
                self._sess.delete(src)
        self._sess.commit()

    def update_all_states(self, state):
        for src in self._sess.query(models.Source):
            src.state = state
        self._sess.commit()

    def shell(self):
        print("[!!] Database connection in 'sess' {}".format(self._sess))
        print("[!!] If you make any changes remember to call sess.commit()")

        sess = self._sess
        utils.get_debugger().set_trace()
        del(sess)  # Just to fix PEP-8 warning

    def search(self, all_states=False, **kwargs):
        query = ldotsa.query_from_params(self._sess, models.Source, **kwargs)
        if not all_states:
            query = query.filter(
                models.Source.state == models.Source.State.NONE)

        return query

    def get_source_by_id(self, id_):
        query = self._sess.query(models.Source)
        query = query.filter(models.Source.id == id_)

        try:
            return query.one()
        except exc.NoResultFound:
            raise SourceNotFound()

    def get_active(self):
        query = self._sess.query(models.Source)
        query = query.filter(~models.Source.state.in_(
            (models.Source.State.NONE, models.Source.State.ARCHIVED)))

        return query

    def update_source_state(self, id_, state):
        source = self.get_source_by_id(id_)
        source.state = state
        self.session.commit()


class ArroyoDownloader:

    def __init__(self, arroyo):
        self._sess = arroyo.session

        backend_mod = importlib.import_module(
            'arroyo.downloaders.' + arroyo.options.get('downloader_name'))
        self._backend = getattr(backend_mod, 'Downloader')(session=self._sess)

    def add(self, *sources):
        for src in sources:
            self._backend.do_add(src)
            src.state = models.Source.State.INITIALIZING
            self._sess.commit()

    def remove(self, *sources):
        translations = {}
        for dler_obj in self._backend.do_list():
            try:
                db_obj = self._backend.translate_item(dler_obj)
                translations[db_obj] = dler_obj
            except downloaders.NoMatchingItem:
                pass

        for src in sources:
            try:
                self._backend.do_remove(translations[src])
                src.state = models.Source.State.NONE
                self._sess.commit()

            except KeyError:
                _logger.warning(
                    "No matching object in backend for '{}'".format(src))

    def list(self):
        ret = []

        for dler_obj in self._backend.do_list():
            # Filter out objects from downloader unknow for the db
            try:
                db_obj = self._backend.translate_item(dler_obj)
            except downloaders.NoMatchingItem as e:
                _logger.warn("No matching db object for {}".format(e.item))
                continue

            # Warn about unknow states
            try:
                dler_state = self._backend.get_state(dler_obj)
            except downloaders.NoMatchingState as e:
                _logger.warn(
                    "No matching state '{}' for {}".format(e.state, db_obj))
                continue

            ret.append(db_obj)
            db_state = db_obj.state
            if db_state != dler_state:
                db_obj.state = dler_state
                SIGNALS['source-state-change'].send(source=db_obj)

        self._sess.commit()
        return ret


class WebUI(FlaskAPI):

    def __init__(self, core):
        super(WebUI, self).__init__(__name__)
        self._core = core

        self.route('/')(self.main)

        self.route('/introspect/')(self.introspect)

        self.route('/browse/')(self.browse)
        self.route('/browse/<string:category>/')(self.browse)
        self.route('/browse/movies/')(self.list_movies)
        self.route('/browse/episodes/')(self.list_series)
        self.route('/browse/series/<string:series>/')(self.list_series)
        self.route('/browse/series/<string:series>/seasons/')(
            self.list_seasons)
        self.route('/browse/series/<string:series>/seasons/<int:season>')(
            self.list_episodes)

        self.route('/search/')(self.search)

        self.route('/downloads/', methods=['GET'])(self.downloads_list)
        self.route('/downloads/', methods=['POST'])(self.downloads_add)
        self.route('/downloads/<string:id_>', methods=['GET'])(
            self.downloads_detail)
        self.route('/downloads/<string:id_>', methods=['DELETE'])(
            self.downloads_remove)

    @staticmethod
    def generic_repr(x):
        return {k: v for (k, v) in x}

    source_repr = generic_repr
    series_repr = generic_repr

    @staticmethod
    def is_safe_type(t):
        try:
            return re.search(r'^[a-z]+(\-[a-z]+)?$', t) is not None
        except:
            return False

    @staticmethod
    def is_safe_language(l):
        try:
            return re.search(r'^[a-z]{2}(\-[a-z]{2,3})*$', l) is not None
        except:
            return False

    def main(self):
        return redirect(url_for('static', filename='index.html'))

    def introspect(self):
        sess = self._core.session

        types = sess.query(models.Source.type).distinct().all()
        types = map(lambda x: x[0], types)

        languages = sess.query(models.Source.language).distinct().all()
        languages = map(lambda x: x[0], languages)

        return {
            'types': [x for x in types if WebUI.is_safe_type(x)],
            'languages': [x for x in languages if WebUI.is_safe_language(x)]
        }

    def browse(self):
        pass

    def list_movies(self):
        pass

    def list_series(self):
        pass

    def list_seasons(self):
        pass

    def list_episodes(self):
        pass

    def search(self):

        # Query parameter

        try:
            q = request.args.get('q', '')
        except IndexError:
            q = ''

        if len(q) < 3:
            return {'error': 'query too vague'}, status.HTTP_400_BAD_REQUEST

        replacements = (
            (' ', '_'),
            ('*', '%'),
            ('.', '_'))

        for (i, o) in replacements:
            q = q.replace(i, o)
        q = '%' + q + '%'

        # All states parameter

        all_states = 'all_states' in request.args

        # Get types and filter parameters

        types = request.args.getlist('type')
        types = [x for x in types if WebUI.is_safe_type(x)]

        languages = request.args.getlist('language')
        languages = [x for x in languages if WebUI.is_safe_language(x)]

        query = self._core.search(all_states=all_states, name_like=q)
        if types:
            query = query.filter(models.Source.type.in_(types))

        if languages:
            query = query.filter(models.Source.language.in_(languages))

        return [WebUI.source_repr(source) for source in query.all()]

    def downloads_list(self):
        self._core.sync()

        return [WebUI.source_repr(x) for x in self._core.downloader.list()]

    def downloads_add(self):
        try:
            id_ = request.data['id']
            source = self._core.get_source_by_id(id_)
        except (KeyError, exc.NoResultFound):
            return {'error': 'Invalid source'}, status.HTTP_404_NOT_FOUND

        self._core.downloader.add(source)
        return {}, status.HTTP_204_NO_CONTENT
        # return {'error': 'unknow error'}, status.HTTP_400_BAD_REQUEST

    def downloads_remove(self, id_):
        try:
            source = self._core.get_source_by_id(id_)
            self._core.downloader.remove(source)
            return {}

        except exc.NoResultFound:
            return {'error': 'Invalid source'}, status.HTTP_404_NOT_FOUND

    def downloads_detail(self):
        pass
