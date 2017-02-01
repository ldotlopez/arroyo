# -*- coding: utf-8 -*-

from arroyo import models


import functools


import babelfish
import guessit


class Mediainfo:
    def __init__(self, app):
        # app.signals.connect('sources-added-batch', self._on_source_batch)
        # app.signals.connect('sources-updated-batch', self._on_source_batch)
        self._app = app
        self.logger = app.logger.getChild('mediainfo')

    @functools.lru_cache(maxsize=16)
    def get_default_language_for_provider(self, provider):
        k = 'plugins.provider.' + provider + '.default-language'
        return self._app.settings.get(k, default=None)

    def get_mediainfo(self, source):
        """
        Get guessed mediainfo from source (mostly from source.name)
        """

        # This table it used in a second phase to get a better guess
        # _fixes = {
        #     'movie': (
        #         ('title', 'year', 'format', 'language'),
        #         ('.avi')
        #     ),
        #     'episode': (
        #         ('title',  # series title, not episode_title
        #          'year',
        #          'season',
        #          'episode',  # number of episode
        #          'format',
        #          'language'),
        #         ('.mp4')
        #     )
        # }

        info = guessit.guessit(source.name, options={'type': source.type})

        # FIXME: Why are we doing this?
        # Do a second guess with fake name
        # if source.type in _fixes:
        #     wanted_fields, expected_ext = _fixes[source.type]
        #     filename, extension = path.splitext(source.name)
        #     if extension != expected_ext:
        #         print("!! Fake guess on {}{}".format(
        #             source.name, expected_ext))
        #         fake_info = guessit.guessit(source.name + expected_ext)

        #         for f in wanted_fields:
        #             if f not in info and f in fake_info:
        #                 info[f] = fake_info[f]
        #     else:
        #         print("OK {}".format(source.name))

        # After all guesses from guessit translate to arroyo-style
        if info.get('type') == 'episode':
            info['series'] = info.pop('title', None)
            info['episode_number'] = info.pop('episode', None)

        info = {k: v for (k, v) in info.items() if v is not None}

        # FIXME: Don't drop, save
        # Drop multiple languages and multiple episode numbers
        for k in ['language', 'part']:
            if isinstance(info.get(k), list):
                msg = 'Drop multiple instances of {key} in {source}'
                msg = msg.format(source=source, key=k)
                self.logger.warning(msg)
                info[k] = info[k][0]

        # Integrate part as episode in season 0
        if 'part' in info:
            if info.get('type') == 'movie':
                msg = "Movie '{source}' has 'part'"
                msg = msg.format(source=source)
                self.logger.warning(msg)

            elif info.get('type') == 'episode':
                if 'season' in info:
                    msg = ("Episode '{source}' has 'part' and 'season'")
                    msg = msg.format(
                        source=source, type=info.get('type') or '(None)'
                    )
                    self.logger.warning(msg)
                else:
                    info['season'] = 0
                    info['episode_number'] = info.pop('part')

            else:
                msg = ("Source '{source}' has 'part' and an unknow "
                       "type: '{type}'")
                msg = msg.format(
                    source=source, type=info.get('type') or '(None)'
                )
                self.logger.warning(msg)

        # Reformat date as episode number for episodes if needed
        if info.get('type', None) == 'episode' and \
           'date' in info:

            # Fix season
            if not info.get('season', None):
                info['season'] = 0

            # Reformat episode number
            if not info.get('episode_number', None):
                info['episode_number'] = '{year}{month:0>2}{day:0>2}'.format(
                    year=info['date'].year,
                    month=info['date'].month,
                    day=info['date'].day)

        # Reformat language as 3let-2let code
        # Note that info also contains a country property but doesn't
        # satisfy our needs: info's country refers to the country where the
        # episode/movie was produced.
        # Example:
        # "Sherlock (US) - 1x01.mp4" vs "Sherlock (UK) - 1x01.mp4"
        # For now only the 3+2 letter code is used.
        #
        # Other sources like 'game of thrones 1x10 multi.avi' are parsed as
        # multilingual (babelfish <Language [mul]>) but throw an exception when
        # alpha2 property is accessed.

        if 'language' in info:
            try:
                info['language'] = '{}-{}'.format(
                    info['language'].alpha3,
                    info['language'].alpha2)
            except babelfish.exceptions.LanguageConvertError as e:
                msg = "Language error in '{source}': {msg}"
                msg = msg.format(source=source.name, msg=e)
                self.logger.warning(msg)
                del info['language']

        else:
            info['language'] = self.get_default_language_for_provider(
                source.provider)

        # Misc fixes. Maybe this needs its own module
        # - 12 Monkeys series
        if info.get('type', None) == 'episode' and \
           info.get('series', None) == 'Monkeys' and \
           source.name.lower().startswith('12 monkeys'):
            info['series'] = '12 Monkeys'

        return info

    def process(self, *sources_and_metas):
        """
        Mediainfo.process takes sources and tries to fill aditional info like
        language, episode or movie relationships
        """
        for x in sources_and_metas:
            if isinstance(x, models.Source):
                src, meta = x, None
            else:
                src, meta = x[0], x[1]

            # if meta:
            #     msg = "Source {source} has metadata: {meta}"
            #     msg = msg.format(source=src, meta=meta)
            #     self.logger.debug(msg)

            # Check for older "APIs"
            if src.type == 'unknown':
                msg = ("Deprecated API: source from {provider} "
                       "with type 'unknow', use (None)")
                msg = msg.format(provider=src.provider)
                self.logger.error(msg)
                src.type = None

            # Sources with 'other' type are not processed
            # *This* is the way to disable mediainfo processing
            if src.type not in ('movie', 'episode', None):
                continue

            info = self.get_mediainfo(src)
            if src.type and src.type != info['type']:
                msg = "Type missmatch for '{source}': {type1} != {type2}"
                msg = msg.format(
                    source=src, type1=src.type, type2=info['type'])
                self.logger.warning(msg)
                continue

            # Update src's type and language
            info_type = info.get('type')
            if src.language is None and info_type is not None:
                try:
                    src.type = info['type']
                except ValueError as e:
                    msg = "Guessed type for {src} is invalid: {type}"
                    msg = msg.format(src=src.name, type=info_type)
                    self.logger.warning(msg)

            info_lang = info.get('language')
            if src.language is None and info_lang is not None:
                try:
                    src.language = info['language']
                except ValueError as e:
                    msg = "Guessed language for {src} is invalid: {language}"
                    msg = msg.format(src=src.name, language=info_lang)
                    self.logger.warning(msg)

            # ... but delete the old ones first
            #
            # Warning: delete operation needs synchronize_session parameter.
            # Possible values are 'fetch' or False, both work as expected but
            # 'fetch' is slightly faster.
            # http://docs.sqlalchemy.org/en/latest/orm/query.html#sqlalchemy.orm.query.Query.delete
            if src.id:
                tags = src.tags
                tags = tags.filter(
                    models.SourceTag.key.startswith('mediainfo.'))
                tags.delete(synchronize_session='fetch')

            # ... ok, create links now
            for (k, v) in info.items():
                if k in ('type', 'language'):
                    continue

                if info['type'] == 'episode' and \
                   k in ('series', 'year', 'season', 'episode-number'):
                    continue

                if info['type'] == 'movie' and \
                   k in ('title', 'year'):
                    continue

                src.tags.append(models.SourceTag('mediainfo.'+k, v))

            # Get or create specilized model. There is no need to check if it
            # gets created, will be added to session when it gets linked to its
            # source
            if src.type in ('movie', 'episode'):
                try:
                    specialized_source = self.get_specialized_source(info)
                except ValueError as e:
                    msg = ("unable to get specilized data for "
                           "'{source}': {reason}")
                    self.logger.warning(msg.format(source=src, reason=e))
                    continue

            # Link source and specialized_source
            if src.type == 'movie':
                src.movie = specialized_source
                src.episode = None

            elif src.type == 'episode':
                src.movie = None
                src.episode = specialized_source

        # Apply changes
        self._app.db.session.commit()

    def get_specialized_source(self, info):
        if info['type'] == 'movie':
            try:
                model = models.Movie
                arguments = {
                    'title': info['title'],
                    'year': int(info.get('year', '0')) or None
                }
            except KeyError:
                msg = "Mediainfo data for movie source is incomplete"
                raise ValueError(msg)

        elif info['type'] == 'episode':
            try:
                model = models.Episode
                arguments = {
                    'series': info['series'],
                    'season': int(info.get('season', '0')),
                    'number': int(info['episode_number']),
                    'year': int(info.get('year', '0')) or None
                }

            except KeyError:
                msg = "Mediainfo data for episode source is incomplete"
                raise ValueError(msg)

        else:
            raise ValueError('invalid type in info data: ' + info['type'])

        ret, created = self._app.db.get_or_create(model, **arguments)
        if created:
            self._app.db.session.add(ret)

        return ret

    def _on_source_batch(self, sender, sources):
        self.process(*sources)
