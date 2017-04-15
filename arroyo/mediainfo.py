# -*- coding: utf-8 -*-

from arroyo import models


import functools
import warnings

import babelfish
import guessit


_SOURCE_TAGS_PREFIX = 'core.'


class Tags:
    AUDIO_CHANNELS = _SOURCE_TAGS_PREFIX + 'audio.channels'
    AUDIO_CODEC = _SOURCE_TAGS_PREFIX + 'audio.codec'
    AUDIO_PROFILE = _SOURCE_TAGS_PREFIX + 'audio.profile'
    BROADCAST_DATE = _SOURCE_TAGS_PREFIX + 'broadcast.date'
    EPISODE_COUNT = _SOURCE_TAGS_PREFIX + 'episode.count'
    EPISODE_DETAILS = _SOURCE_TAGS_PREFIX + 'episode.details'
    EPISODE_TITLE = _SOURCE_TAGS_PREFIX + 'episode.title'
    GUESSIT_OTHER = _SOURCE_TAGS_PREFIX + 'guessit.other'
    GUESSIT_UUID = _SOURCE_TAGS_PREFIX + 'guessit.uuid'
    MEDIA_CONTAINER = _SOURCE_TAGS_PREFIX + 'media.container'
    MEDIA_COUNTRY = _SOURCE_TAGS_PREFIX + 'media.country'
    MEDIA_LANGUAGE = _SOURCE_TAGS_PREFIX + 'media.language'
    MIMETYPE = _SOURCE_TAGS_PREFIX + 'mimetype'
    RELEASE_DISTRIBUTORS = _SOURCE_TAGS_PREFIX + 'release.distributors'
    RELEASE_GROUP = _SOURCE_TAGS_PREFIX + 'release.group'
    RELEASE_PROPER = _SOURCE_TAGS_PREFIX + 'release.proper'
    STREAMING_SERVICE = _SOURCE_TAGS_PREFIX + 'streaming.service'
    VIDEO_CODEC = _SOURCE_TAGS_PREFIX + 'video.codec'
    VIDEO_FORMAT = _SOURCE_TAGS_PREFIX + 'video.format'
    VIDEO_SCREEN_SIZE = _SOURCE_TAGS_PREFIX + 'video.screen-size'

    @classmethod
    def values(cls):
        for x in dir(cls):
            if x[0] == '_':
                continue

            value = getattr(cls, x)
            if (not isinstance(value, str) or
                    not value.startswith(_SOURCE_TAGS_PREFIX)):
                continue

            yield value

METADATA_RULES = [
    ('audio_channels', Tags.AUDIO_CHANNELS),
    ('audio_codec', Tags.AUDIO_CODEC),
    ('audio_profile', Tags.AUDIO_PROFILE),
    ('container', Tags.MEDIA_CONTAINER),
    ('country', Tags.MEDIA_COUNTRY),
    ('date', Tags.BROADCAST_DATE),
    ('episode_count', Tags.EPISODE_COUNT),
    ('episode_details', Tags.EPISODE_DETAILS),
    ('episode_title', Tags.EPISODE_TITLE),
    ('format', Tags.VIDEO_FORMAT),
    ('language', Tags.MEDIA_LANGUAGE),
    ('mimetype', Tags.MIMETYPE),
    ('proper_count', Tags.RELEASE_PROPER, lambda x: int(x) > 0),
    ('other', Tags.GUESSIT_OTHER),
    ('release_distributors', Tags.RELEASE_DISTRIBUTORS),
    ('release_group', Tags.RELEASE_GROUP),
    ('screen_size', Tags.VIDEO_SCREEN_SIZE),
    ('streaming_service', Tags.STREAMING_SERVICE),
    ('uuid', Tags.GUESSIT_UUID),
    ('video_codec', Tags.VIDEO_CODEC),
]

KNOWN_DISTRIBUTORS = [
    'glodls',
    'ethd',
    'ettv',
    'eztv',
    'rartv'
]  # keep lower case!!


class ParseError(Exception):
    """
    Exception raised for unparseable or unidentificable strings
    """
    pass


class UnknownEntityTypeError(Exception):
    """
    Exception raised for entity datas with unsupported type field
    """
    pass


class IncompleteEntityDataError(Exception):
    pass


def extract_items(orig, rules):
    ret = {}

    for rule in rules:
        if len(rule) == 3:
            orig_key, dest_key, fn = rule
        else:
            orig_key, dest_key = rule
            fn = None

        if orig_key in orig:
            value = orig.pop(orig_key)
            if fn:
                value = fn(value)

            ret[dest_key] = value

    return ret


def extract_entity_data_from_info(info):
    table = {
        'episode': (models.Episode, ['series', 'year', 'season', 'number']),
        'movie': (models.Movie, ['title', 'year'])
    }

    try:
        type_ = info['type']
    except KeyError as e:
        msg = 'Missing type information'
        raise UnknownEntityTypeError(msg)

    if type_ not in table:
        raise UnknownEntityTypeError(type_)

    model_class, available_items = table[type_]

    ret = {'type': info.pop('type')}
    ret.update({
        key: model_class.normalize(key, info.pop(key))
        for key in available_items
        if key in info
    })

    return ret


def entity_data_has_fields(data, keys_map):
    try:
        type_ = data['type']
    except KeyError as e:
        msg = 'Missing type information'
        raise UnknownEntityTypeError(msg)

    if type_ not in keys_map:
        raise UnknownEntityTypeError(type_)

    return all([
        x in data and data[x] != ''
        for x in keys_map[type_]
    ])


def entity_data_is_complete(data):
    """
    Check if entity_data has enoguht information to build a complete entity
    model
    """
    fields_map = {
        'episode': ['series', 'season', 'number'],
        'movie': ['title']
    }

    return entity_data_has_fields(data, fields_map)


def entity_data_is_confident(data):
    fields_map = {
        'episode': ['series', 'season', 'number'],
        'movie': ['title', 'year']
    }

    return entity_data_has_fields(data, fields_map)


def _guessit_parse(name, extra_tags=None, type_hint=None):
    """
    Parse "backend using guessit"
    """

    # We preprocess name to extract distributors
    # (distributors != release-teams)
    release_distributors = set()
    for dist in KNOWN_DISTRIBUTORS:
        tag = '[' + dist + ']'
        idx = name.lower().find(tag)
        if idx == -1:
            continue

        name = (name[:idx] + name[idx+len(tag):]).strip()
        release_distributors.add(dist)

    # Process via guessit (options.type is integrated into returned info by
    # guessit.guessit, no need to manually add it
    info = guessit.guessit(name, options={'type': type_hint})

    # Errors: 'part' is not supported
    if 'part' in info:
        msg = ("Name '{name}' has a 'part' component. This is unsupported due "
               "to its complexity")
        msg = msg.format(name=name)
        raise ParseError(msg)

    # Fixes: Insert distributors again
    if release_distributors:
        info['release_distributors'] = list(release_distributors)

    # Fixes: Reformat date as episode number for episodes if needed
    if info['type'] == 'episode' and 'date' in info:
        if not info.get('season'):
            info['season'] = 0

        # Reformat episode number
        if not info.get('episode'):
            info['episode'] = '{year}{month:0>2}{day:0>2}'.format(
                year=info['date'].year,
                month=info['date'].month,
                day=info['date'].day)

    # Fixes: Rename episode fields
    if info['type'] == 'episode':
        if 'episode' in info:
            info['number'] = info.pop('episode')
        if 'title' in info:
            info['series'] = info.pop('title')

    # Fixes: Normalize language
    if isinstance(info.get('language'), list):
        # msg = 'Drop multiple instances of {key} in {name}'
        # msg = msg.format(name=name, key=k)
        # self.logger.warning(msg)
        info['language'] = info['language'][0]

    # Fixes: Normalize language value
    if 'language' in info:
        try:
            info['language'] = '{}-{}'.format(
                info['language'].alpha3,
                info['language'].alpha2)
        except babelfish.exceptions.LanguageConvertError as e:
            # FIXME: Log this error
            # msg = "Language error in '{name}': {msg}"
            # msg = msg.format(name=name, msg=e)
            # self.logger.warning(msg)
            del info['language']

    return info


def parse(name, extra_tags=None, type_hint=None):
    """
    Parse name and extra_tags to find entity_data and metadata
    """
    if extra_tags is None:
        extra_tags = {}

    # For now we only support one parser provider: guessit
    info = _guessit_parse(name, extra_tags=extra_tags, type_hint=type_hint)

    # Extract two sets of information
    try:
        entity_data = extract_entity_data_from_info(info)
    except UnknownEntityTypeError as e:
        raise ParseError from e

    if not entity_data_is_confident(entity_data) and not type_hint:
        raise ParseError('Incomplete data')

    metadata = extract_items(info, METADATA_RULES)

    # FIXME: Using warnings module instead of logger
    if info:
        leftovers = ['{}={}'.format(k, v) for k, v in info.items()]
        leftovers = ', '.join(leftovers)
        msg = "BUG: Unhandled information for {type} '{name}': {leftovers}."
        msg = msg.format(
            name=name,
            leftovers=leftovers,
            type=entity_data['type'],
        )
        warnings.warn(msg)

    return entity_data, metadata


class Mediainfo:
    def __init__(self, app):
        self.app = app
        self.logger = app.logger.getChild('mediainfo')

        app.signals.connect('sources-added-batch', self._on_source_batch)
        app.signals.connect('sources-updated-batch', self._on_source_batch)

    def _on_source_batch(self, sender, sources):
        self.process(*sources)

    @functools.lru_cache(maxsize=16)
    def default_language_for_provider(self, provider):
        k = 'plugins.provider.' + provider + '.default-language'
        return self.app.settings.get(k, default=None)

    def entity_from_data(self, entity_data):
        # Create entity model
        if entity_data['type'] == 'episode':
            model_class = models.Episode

        elif entity_data['type'] == 'movie':
            model_class = models.Movie

        else:
            msg = "Unsupported entity type: '{type}'"
            msg = msg.format(type=entity_data['type'])
            raise ValueError(msg)

        if not entity_data_is_complete(entity_data):
            raise IncompleteEntityDataError()

        # Complete data with NULLs before quering the database
        if model_class == models.Episode:
            entity_data = {
                k: entity_data.get(k, None)
                for k in ['series', 'year', 'season', 'number']
            }

        elif model_class == models.Movie:
            entity_data = {
                k: entity_data.get(k, None)
                for k in ['title', 'year']
            }
        else:
            raise ValueError()

        model, dummy = self.app.db.get_or_create(model_class,
                                                 **entity_data)
        assert not isinstance(model, list)

        return model

    def link_source_with_entity(self, source, entity):
        attrs = ['episode', 'movie']

        if source.type == 'episode':
            attr = 'episode'
        elif source.type == 'movie':
            attr = 'movie'
        else:
            msg = "Unsupported entity type: '{type}'"
            msg = msg.format(type=source.type)
            raise ValueError(msg)

        for x in attrs:
            value = entity if x == attr else None
            setattr(source, x, value)

    def process(self, *sources_and_tags):
        for x in sources_and_tags:
            if isinstance(x, models.Source):
                src, tags = x, None
            else:
                src, tags = x[0], x[1]

            # Check for older "APIs"
            if src.type == 'unknown':
                msg = ("Deprecated API: source from {provider} "
                       "with type 'unknow', use (None)")
                msg = msg.format(provider=src.provider)
                self.logger.error(msg)
                src.type = None

            # Extract entity data
            try:
                entity_data, metadata = parse(
                    src.name, extra_tags=tags, type_hint=src.type)

            except UnknownEntityTypeError as e:
                msg = "Unknow entity type in '{source}': {e}"
                msg = msg.format(source=src, e=str(e))
                self.logger.warning(msg)
                continue

            except ParseError as e:
                msg = "Unable to indentify entity in '{source}': {e}"
                msg = msg.format(source=src, e=str(e))
                self.logger.warning(msg)
                continue

            # Update source type
            src.type = entity_data['type']

            # Update source type if it's missing
            if not src.language:
                src.language = self.default_language_for_provider(src.provider)

            # Create entity from data
            try:
                entity = self.entity_from_data(entity_data)
                self.link_source_with_entity(src, entity)
                self.app.db.session.add(entity)
            except IncompleteEntityDataError as e:
                msg = "Incomplete entity data for '{source}'"
                msg = msg.format(source=src.name)
                self.logger.warning(msg)

            # Delete old tags
            #
            # Warning: delete operation needs synchronize_session parameter.
            # Possible values are 'fetch' or False, both work as expected but
            # 'fetch' is slightly faster.
            # http://docs.sqlalchemy.org/en/latest/orm/query.html#sqlalchemy.orm.query.Query.delete
            src.tags.filter(
                models.SourceTag.key.in_(Tags.values())
            ).delete(synchronize_session='fetch')

            # Create new tags
            for (k, v) in metadata.items():
                src.tags.append(models.SourceTag(k, v))
