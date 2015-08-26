# -*- coding: utf-8 -*-

from os import path

import babelfish
import guessit

from arroyo import models


class Mediainfo:
    def __init__(self, app):
        app.signals.connect('sources-added-batch', self._on_source_batch)
        app.signals.connect('sources-updated-batch', self._on_source_batch)
        self._app = app
        self._logger = app.logger.getChild('mediainfo')

    def _on_source_batch(self, sender, sources):
        self.process(*sources)

    def _get_mediainfo(self, source):
        # TODO:
        # - 'Jimmy Fallon 2014 10 14 Emma Stone HDTV x264-CROOKS' is not
        #   guessed correctly by guess_episode_info but not by guess_file_info
        # - Fix:
        # In [3]: pp(guessit.guess_file_info(
        #   'The 100 - Temporada 2 [HDTV][Cap.201][V.O.Sub. Español Castellano].avi'  # nopep8
        # ))
        # {'container': 'avi',
        #  'episodeNumber': 100,
        #  'format': 'HDTV',
        #  'mimetype': 'video/x-msvideo',
        #  'releaseGroup': 'Cap',
        #  'series': 'The', <----- FIXME
        #  'subtitleLanguage': [<Language [es]>],
        #  'title': 'Temporada 2',
        #  'type': 'episode',
        #  'unidentified': ['Castellano', 'V O']}

        if source.type == 'movie':
            info = guessit.guess_movie_info(source.name)
        elif source.type == 'episode':
            info = guessit.guess_episode_info(source.name)
        else:
            info = guessit.guess_file_info(source.name)

        # The spanish scene is SO bad doing releases. For this reason we need
        # to trick guessit to get correct info.
        # See this:
        #
        # ipdb> pp(guessit.guess_file_info(
        #    'Dominion (US) - Temporada 1 [HDTV][Cap.104][Español Castellano].avi'  # nopep8
        # ))
        # {'container': 'avi',
        #  'country': <Country [US]>,
        #  'episodeNumber': 4,
        #  'format': 'HDTV',
        #  'language': [<Language [es]>],
        #  'mimetype': 'video/x-msvideo',
        #  'releaseGroup': 'Cap',
        #  'season': 1,
        #  'series': 'Dominion (US)',
        #  'title': 'Castellano',
        #  'type': 'episode',
        #  'unidentified': ['Temporada 1']}
        #
        # ipdb> pp(guessit.guess_file_info(
        #    'Dominion (US) - Temporada 1 [HDTV][Cap.104][Español Castellano]'
        # ))
        # {'country': <Country [US]>,
        #  'episodeNumber': 4,
        #  'extension': '104][español castellano]',
        #  'format': 'HDTV',
        #  'releaseGroup': 'Cap',
        #  'season': 1,
        #  'type': 'episode',
        #  'unidentified': ['Dominion', 'p', 'Temporada 1']}

        fixes = {
            'movie': (
                ('title', 'year'),
                ('.avi')
            ),
            'episode': (
                ('series', 'year', 'season', 'episodeNumber'),
                ('.mp4')
            )
        }

        if source.type in fixes:
            wanted_fields, expected_ext = fixes[source.type]
            filename, extension = path.splitext(source.name)

            if extension != expected_ext:
                try:
                    fake_info = guessit.guess_file_info(
                        source.name + expected_ext)
                except RuntimeError:
                    # See: https://github.com/wackou/guessit/issues/209
                    msg = "Trap RuntimeError: {name}"
                    msg = msg.format(name=source.name + expected_ext)
                    self._logger.critical(msg)

                for f in wanted_fields:
                    if f not in info and f in fake_info:
                        info[f] = fake_info[f]

        if 'date' in info and \
           info.get('type', None) == 'episode':
            if not info.get('season', None):
                info['season'] = -1
            if not info.get('episodeNumber', None):
                info['episodeNumber'] = '{year}{month}{day}'.format(
                    year=info['date'].year,
                    month=info['date'].month,
                    day=info['date'].day)

        if 'language' in info:
            # FIXME: Handle all languages
            info['language'] = '{}-{}'.format(
                info['language'][0].alpha3,
                info['language'][0].alpha2)

        # Misc fixes. Maybe this needs its own module
        # 12 Monkeys series
        if info.get('type', None) == 'episode' and \
           info.get('series', None) == 'Monkeys' and \
           source.name.lower().startswith('12 monkeys'):
            info['series'] = '12 Monkeys'

        return info

    def _get_specilized_source(self, info):
        if info['type'] == 'movie':
            try:
                model = models.Movie
                arguments = {
                    'title': info['title'],
                    'year': info.get('year', None)
                }
            except KeyError:
                raise ValueError('info data for movie source is incomplete')

        elif info['type'] == 'episode':
            try:
                model = models.Episode
                arguments = {
                    'series': info['series'],
                    'season': info.get('season', -1),
                    'number': info['episodeNumber'],
                    'year': info.get('year', None)
                }
            except KeyError:
                raise ValueError('info data for episode source is incomplete')

        else:
            raise ValueError('invalid type in info data: ' + info['type'])

        return self._app.db.get_or_create(model, **arguments)

    def process(self, *sources):
        for src in sources:
            try:
                info = self._get_mediainfo(src)
            except babelfish.exceptions.LanguageConvertError as e:
                msg = 'babelfish language error with \'{source}\': {msg}'
                msg = msg.format(source=src, msg=e)
                self._logger.warning(msg)
                continue

            # Give up if info's type is unknow
            if info.get('type', 'unknown') == 'unknown':
                msg = "unknown type for '{source}'"
                self._logger.warning(msg.format(source=src))
                continue

            # Update source.type only if it is unknow
            if src.type is None:
                src.type = info['type']

            # Fix language
            # info also contains a country property but doesn't satisfy our
            # needs.
            # info's country refers to the country where the episode/movie whas
            # produced. Example:
            # "Sherlock (US) - 1x01.mp4" vs "Sherlock (UK) - 1x01.mp4"
            # For now only the 3 letter code is used.
            if src.language is None and 'language' in info:
                src.language = info['language']

            elif src.language is not None:
                info['language'] = src.language

            src.tags.\
                filter(models.SourceTag.key.startswith('mediainfo.')).\
                delete(synchronize_session='fetch')

            for (k, v) in info.items():
                if k in ('type', 'language'):
                    continue

                if info['type'] == 'episode' and \
                   k in ('series', 'year', 'season', 'episodeNumber'):
                    continue

                if info['type'] == 'movie' and \
                   k in ('title', 'year'):
                    continue

                src.tags.append(models.SourceTag('mediainfo.'+k, v))

            # Create specilized model
            try:
                specilized_source, created = self._get_specilized_source(info)
                if created:
                    self._app.db.session.add(specilized_source)
            except ValueError as e:
                msg = "unable to get specilized data for '{source}': {reason}"
                self._logger.warning(msg.format(source=src, reason=e))
                continue

            # Link source and specialized_source
            if info['type'] == 'movie':
                src.movie = specilized_source
                src.episode = None

            elif info['type'] == 'episode':
                src.movie = None
                src.episode = specilized_source

        # Apply changes
        self._app.db.session.commit()
