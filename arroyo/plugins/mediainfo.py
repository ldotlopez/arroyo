from os import path

import guessit
from ldotcommons import logging

from arroyo import models, plugins
from arroyo.app import app


_logger = logging.get_logger('metainfo')


def get_mediainfo(source):
    # TODO:
    # - 'Jimmy Fallon 2014 10 14 Emma Stone HDTV x264-CROOKS' is not guessed
    #   correctly by guess_episode_info but not by guess_file_info
    # - Fix:
    # In [3]: pp(guessit.guess_file_info(
    # 'The 100 - Temporada 2 [HDTV][Cap.201][V.O.Sub. Español Castellano].avi'
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

    # The spanish scene is SO bad doing releases. For this reason we need to
    # trick guessit to get correct info.
    # See this:
    #
    # ipdb> pp(guessit.guess_file_info(
    #    'Dominion (US) - Temporada 1 [HDTV][Cap.104][Español Castellano].avi'
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
            ('title', 'year', 'language'),
            ('.avi')
        ),
        'episode': (
            ('series', 'year', 'language', 'season', 'episodeNumber'),
            ('.mp4')
        )
    }

    if source.type in fixes:
        wanted_fields, expected_ext = fixes[source.type]
        filename, extension = path.splitext(source.name)

        if extension != expected_ext:
            fake_info = guessit.guess_file_info(source.name + expected_ext)
            for f in wanted_fields:
                if f not in info and f in fake_info:
                    info[f] = fake_info[f]

    if 'language' in info:
        # FIXME: Handle all languages
        info['language'] = info['language'][0].alpha3

    return info


def get_specilized_source(info):
    if info['type'] == 'movie':
        try:
            model = models.Movie
            arguments = {
                'title': info['title'],
                'year': info.get('year', None),
                'language': info.get('language', None)
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
                'year': info.get('year', None),
                'language': info.get('language', None)
            }
        except KeyError:
            raise ValueError('info data for episode source is incomplete')

    else:
        raise ValueError('invalid type in info data: ' + info['type'])

    # arguments = {k: v for (k, v) in arguments.items() if v is not None}

    obj = app.db.get(model, **arguments)

    if obj is not None:
        created = False
    else:
        obj = model(**arguments)
        created = True

    return obj, created


@app.register('command')
class Mediainfo:
    name = 'mediainfo'
    help = 'Guess mediainfo from sources'
    arguments = (
        plugins.argument(
            '-i', '--item',
            dest='item',
            help='Run mediainfo on selected item'
        ),
    )

    # def __init__(self):
    #     app.signals['source-added'].connect(self.on_source)
    #     app.signals['source-updated'].connect(self.on_source)

    # def on_source(self, *args, **kwargs):
    #     print("Args:", repr(args), "kwargs:", repr(kwargs))

    def run(self):
        item = app.arguments.item

        if item:
            srcs = [app.db.get(models.Source, id=item)]
        else:
            srcs = app.db.session.query(models.Source)

        for src in srcs:
            info = get_mediainfo(src)

            # Give up if info's type is unknow
            if info['type'] == 'unknown':
                msg = "unknown type for {source}"
                _logger.warning(msg.format(source=src))
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
                src.language = info['language'].alpha3

            elif src.language is not None:
                info['language'] = src.language

            # Create specilized model
            try:
                specilized_source, created = get_specilized_source(info)
                if created:
                    app.db.session.add(specilized_source)
            except ValueError as e:
                msg = "unable to get specilized data for '{source}': {reason}"
                _logger.warning(msg.format(source=src, reason=e))
                continue

            # Link source and specialized_source
            if info['type'] == 'movie':
                src.movie = specilized_source
                src.episode = None

            elif info['type'] == 'episode':
                src.movie = None
                src.episode = specilized_source

        # Apply changes
        app.db.session.commit()
