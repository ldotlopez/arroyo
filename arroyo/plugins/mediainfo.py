import guessit

from ldotcommons import logging

from arroyo import models, plugins
from arroyo.app import app


_logger = logging.get_logger('metainfo')


def get_mediainfo(source):
    # TODO:
    # - 'Jimmy Fallon 2014 10 14 Emma Stone HDTV x264-CROOKS' is not guessed
    #   correctly by guess_episode_info but not by guess_file_info

    info = guessit.guess_file_info(source.name)

    # Fix language
    if 'language' in info:
        info['language'] = [x.english_name for x in info['language']]

    # FIXME: Ok, I have no idea what the hell is doing this code exactly.
    # It comes from an ancient and obscure code and I remember it was very
    # useful, so I'm keeping it
    ext_fixes = (
        ('movie',
            ('title',),
            '.avi'),
        ('episode',
            ('series', 'season', 'episodeNumber'),
            '.mp4')
    )
    for (type_, fields, ext) in ext_fixes:
        if info['type'] == type_ and fields[0] not in info:
            info2 = guessit.guess_file_info(source.name + ext)
            for field in fields:
                try:
                    info[field] = info2[field]
                except KeyError:
                    pass

    return info


def get_specilized_source(info):
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
                'episode_number': info['episodeNumber'],
                'year': info.get('year', None)
            }
        except KeyError:
            raise ValueError('info data for episode source is incomplete')

    else:
        raise ValueError('invalid type in info data: ' + info['type'])

    arguments = {k: v for (k, v) in arguments.items() if v is not None}

    obj = app.db.get(model, **arguments)
    if obj is not None:
        created = False
    else:
        obj = model(**arguments)
        created = True

    return obj, created


class Mediainfo(plugins.Command):
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

            #
            # Update source with mediainfo
            #

            # Fix source's type
            # FIXME: Move this into model
            if src.type in ('unknown', 'unknow'):
                src.type = None

            # Give up if info's type is unknow
            if info['type'] == 'unknown':
                msg = "unknown type for {source}"
                _logger.warning(msg.format(source=src))
                continue

            # Update source.type only if it is unknow
            if src.type is None:
                src.type = info['type']

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

app.register_command(Mediainfo)
