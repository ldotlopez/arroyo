# -*- coding: utf-8 -*-

import hashlib
import re
from urllib import parse
import sys


from ldotcommons.sqlalchemy import Base
from ldotcommons import keyvaluestore, utils
from sqlalchemy import schema, Column, Integer, String, ForeignKey
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship, backref


Variable = keyvaluestore.keyvaluemodel('Variable', Base, dict({
    '__table_args__': (schema.UniqueConstraint('key'),)
    }))


SourceTag = keyvaluestore.keyvaluemodel(
    'SourceTag',
    Base,
    dict({
        '__tablename__': 'sourcetag',
        '__table_args__': (schema.UniqueConstraint('source_id', 'key'),),
        'source_id': Column(Integer, ForeignKey('source.id',
                                                ondelete="CASCADE")),
        'source': relationship("Source",
                               backref=backref("tags",
                                               lazy='dynamic',
                                               cascade="all, delete, delete-orphan"))  # nopep8
    }))


class Source(Base):
    __tablename__ = 'source'

    # TODO: rethink those classes
    class State:
        NONE = 0
        INITIALIZING = 1
        QUEUED = 2
        PAUSED = 3
        DOWNLOADING = 4
        SHARING = 5
        DONE = 6
        ARCHIVED = 7

    class Formats:
        DEFAULT = '{name}'
        DETAIL = (
            "{name} "
            "(lang: {language}, size: {size}, ratio: {seeds}/{leechers})"
        )

    _SYMBOL_TABLE = {
        State.INITIALIZING: '⋯',
        State.QUEUED: '⋯',
        State.PAUSED: '‖',
        State.DOWNLOADING: '↓',
        State.SHARING: '⇅',
        State.DONE: '✓',
        State.ARCHIVED: '▣'
    }

    id = Column(Integer, primary_key=True)
    urn = Column(String, unique=True)
    name = Column(String, nullable=False)
    uri = Column(String, nullable=False, unique=True)
    created = Column(Integer, nullable=False)
    last_seen = Column(Integer, nullable=False)
    size = Column(Integer, nullable=True)
    provider = Column(String, nullable=False)

    seeds = Column(Integer, nullable=True)
    leechers = Column(Integer, nullable=True)
    state = Column(Integer, nullable=False, default=State.NONE)

    _type = Column('type', String, nullable=True)
    _language = Column('language', String, nullable=True)

    episode_id = Column(Integer,
                        ForeignKey('episode.id', ondelete="SET NULL"),
                        nullable=True)
    episode = relationship("Episode",
                           uselist=False,
                           backref=backref("sources", lazy='dynamic'))

    movie_id = Column(Integer,
                      ForeignKey('movie.id', ondelete="SET NULL"),
                      nullable=True)
    movie = relationship("Movie",
                         uselist=False,
                         backref=backref("sources", lazy='dynamic'))

    @staticmethod
    def from_data(name, sha1=None, **kwargs):
        if not sha1:
            sha1 = hashlib.sha1(name.encode('utf-8')).hexdigest()

        now = utils.now_timestamp()
        kwargs['created'] = kwargs.get('created', now)
        kwargs['last_seen'] = kwargs.get('last_seen', now)

        if 'provider' not in kwargs:
            kwargs['provider'] = 'mock'

        ret = Source()
        ret.name = name
        ret.urn = 'urn:btih:' + sha1
        ret.uri = 'magnet:?xt={urn}&dn={dn}'.format(
            urn=ret.urn,
            dn=parse.quote_plus(name))

        for (attr, value) in kwargs.items():
            if hasattr(ret, attr):
                setattr(ret, attr, value)

        return ret

    @property
    def tag_dict(self):
        return {x.key: x.value for x in self.tags.all()}

    @hybrid_property
    def age(self):
        return utils.now_timestamp() - self.created

    @hybrid_property
    def entity(self):
        return (
            self.episode or
            self.movie
        )

    @hybrid_property
    def is_active(self):
        return self.state not in [Source.State.NONE, Source.State.ARCHIVED]

    @hybrid_property
    def language(self):
        return self._language

    @language.setter
    def language(self, value):
        if not _check_language(value):
            raise ValueError(value)

        self._language = value.lower() if value else None

    @hybrid_property
    def share_ratio(self):
        if self.seeds is None or self.leechers is None:
            return 0

        if self.leechers == 0:
            return sys.maxsize

        return self.seeds / self.leechers

    @property
    def state_name(self):
        for attr in [x for x in dir(Source.State)]:
            if getattr(Source.State, attr) == self.state:
                return attr.lower()
        return "unknow-{}".format(self.state)

    @property
    def state_symbol(self):
        return self._SYMBOL_TABLE.get(self.state, ' ')

    @hybrid_property
    def type(self):
        return self._type

    @type.setter
    def type(self, value):
        if not _check_type(value):
            raise ValueError(value)

        self._type = value.lower() if value else None

    def as_dict(self):
        return {k: v for (k, v) in self}

    def format(self, fmt=Formats.DEFAULT, extra_data={}):
        data = self.as_dict()
        data['seeds'] = data.get('seeds') or '-'
        data['leechers'] = data.get('leechers') or '-'
        data['language'] = data.get('language') or '--- --'

        data.update(extra_data)

        return fmt.format(**data)

    def __eq__(self, other):
        return self.id.__eq__(other.id)

    def __hash__(self):
        return self.id.__hash__()

    def __iter__(self):
        keys = [
            'age', 'created', 'entity', 'episode', 'episode_id', 'id',
            'is_active', 'language', 'last_seen', 'leechers', 'movie',
            'movie_id', 'name', 'provider', 'seeds', 'share_ratio', 'size',
            'state', 'state_symbol', 'tags', 'type', 'type', 'uri', 'urn'
        ]

        for k in keys:
            yield (k, getattr(self, k))

        # if self.entity:
        #     yield ('entity', self.entity.__class__.__name__.lower())
        #     yield ('entity_id', self.entity.id)

    def __lt__(self, other):
        return self.id.__lt__(other.id)

    def __str__(self):
        return self.__unicode__()

    def __repr__(self):
        return "<Source {id} ('{name}')>".format(
            id=self.id,
            name=self.name)

    def __unicode__(self):
        return self.format(self.Formats.DEFAULT)


class Selection(Base):
    __tablename__ = 'selection'

    id = Column(Integer, primary_key=True)
    type = Column(String(50))

    source_id = Column(Integer, ForeignKey('source.id', ondelete="CASCADE"),
                       nullable=False)
    source = relationship("Source")


class EpisodeSelection(Selection):
    episode_id = Column(Integer,
                        ForeignKey('episode.id', ondelete="CASCADE"),
                        nullable=True)
    episode = relationship("Episode",
                           backref=backref("selection",
                                           cascade="all, delete",
                                           uselist=False))

    __mapper_args__ = {
        'polymorphic_identity': 'episode'
    }

    def __repr__(self):
        fmt = '<EpisodeSelection {id} episode:{episode} <-> source:{source}'
        return fmt.format(
            id=self.id,
            episode=self.episode.__repr__(),
            source=self.source.__repr__())


class Episode(Base):
    __tablename__ = 'episode'
    __table_args__ = (
        schema.UniqueConstraint('series', 'year', 'season',
                                'number'),
    )

    id = Column(Integer, primary_key=True)

    series = Column(String, nullable=False)
    year = Column(Integer, nullable=True)
    season = Column(Integer, nullable=False)
    # guessit returns episodeList attribute if more than one episode is
    # detected, take care of this
    number = Column(Integer, nullable=False)

    SELECTION_MODEL = EpisodeSelection

    class Formats:
        DEFAULT = '{series_with_year} S{season:02d}E{number:02d}'

    @staticmethod
    def from_data(series, season, number, **kwargs):
        ret = Episode()
        ret.series = series
        ret.title = season
        ret.number = number

        for (attr, value) in kwargs.items():
            if hasattr(ret, attr):
                setattr(ret, attr, value)

        return ret

    def as_dict(self):
        return {k: v for (k, v) in self}

    def format(self, fmt=Formats.DEFAULT, extra_data={}):
        d = self.as_dict()

        if self.year:
            series_with_year = "{series} ({year})"
        else:
            series_with_year = "{series}"

        d['series_with_year'] = series_with_year.format(**d)
        d.update(**extra_data)

        return fmt.format(**d)

    def __iter__(self):
        keys = ['id', 'series', 'year', 'season', 'number']
        for k in keys:
            yield (k, getattr(self, k))

    def __repr__(self):
        d = {}
        if self.year is None:
            d['year'] = '----'

        return self.format(
            fmt="<Episode #{id} {series} ({year}) S{season:02d}E{number:02d})>",
            extra_data=d)

    def __str__(self):
        return self.__unicode__()

    def __unicode__(self):
        return self.format()


class MovieSelection(Selection):
    movie_id = Column(Integer,
                      ForeignKey('movie.id', ondelete="CASCADE"),
                      nullable=True)
    movie = relationship("Movie",
                         backref=backref("selection",
                                         cascade="all, delete",
                                         uselist=False))

    __mapper_args__ = {
        'polymorphic_identity': 'movie'
    }

    def __repr__(self):
        fmt = '<MovieSelection {id} movie:{movie} <-> source:{source}'
        return fmt.format(
            id=self.id,
            movie=self.movie.__repr__(),
            source=self.source.__repr__())


class Movie(Base):
    __tablename__ = 'movie'
    __table_args__ = (
        schema.UniqueConstraint('title', 'year'),
    )

    id = Column(Integer, primary_key=True)

    title = Column(String, nullable=False)
    year = Column(Integer, nullable=True)

    SELECTION_MODEL = MovieSelection

    class Formats:
        DEFAULT = '{title_with_year}'

    @staticmethod
    def from_data(title, **kwargs):
        ret = Movie()
        ret.title = title

        for (attr, value) in kwargs.items():
            if hasattr(ret, attr):
                setattr(ret, attr, value)

        return ret

    def as_dict(self):
        return {k: v for (k, v) in self}

    def format(self, fmt=Formats.DEFAULT, extra_data={}):
        d = self.as_dict()

        if self.year:
            title_with_year = "{title} ({year})"
        else:
            title_with_year = "{title}"

        d['title_with_year'] = title_with_year.format(**d)
        d.update(**extra_data)

        return fmt.format(**d)

    def __iter__(self):
        keys = ['id', 'title', 'year']
        for k in keys:
            yield (k, getattr(self, k))

    def __repr__(self):
        d = {}
        if self.year is None:
            d['year'] = '----'

        return self.format(
            fmt="<Movie #{id} {title} ({year})>",
            extra_data=d)

    def __str__(self):
        return self.__unicode__()

    def __unicode__(self):
        return self.format()


def _check_language(lang):
    return (lang is None or re.match(r'^...(\-..)?$', lang))


def _check_type(typ):
    return typ in (
        None,
        'application',
        'book',
        'episode',
        'game',
        'movie',
        'music',
        'other',
        'xxx',
    )
