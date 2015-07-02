# -*- coding: utf-8 -*-
# [SublimeLinter pep8-max-line-length:119]
# vim: set fileencoding=utf-8 :

import hashlib
import re
from urllib import parse
import sys

from ldotcommons.sqlalchemy import Base
from ldotcommons import keyvaluestore, utils
from sqlalchemy import schema, Column, Integer, String, ForeignKey
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship, backref


Variable = keyvaluestore.keyvaluemodel('Variable', Base)


class Source(Base):
    __tablename__ = 'source'

    class State:
        NONE = 0
        INITIALIZING = 1
        QUEUED = 2
        PAUSED = 3
        DOWNLOADING = 4
        SHARING = 5
        DONE = 6
        ARCHIVED = 7

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

    @hybrid_property
    def superitem(self):
        return (
            self.episode or
            self.movie
        )

    @hybrid_property
    def age(self):
        return utils.now_timestamp() - self.created

    @hybrid_property
    def share_ratio(self):
        if self.seeds is None or self.leechers is None:
            return 0

        if self.leechers == 0:
            return sys.maxsize

        return self.seeds / self.leechers

    #
    # Type property
    #
    @hybrid_property
    def type(self):
        return self._type

    @type.setter
    def type(self, value):
        if not _check_type(value):
            raise ValueError(value)

        self._type = value.lower() if value else None

    #
    # Language property
    #
    @hybrid_property
    def language(self):
        return self._language

    @language.setter
    def language(self, value):
        if not _check_language(value):
            raise ValueError(value)

        self._language = value.lower() if value else None

    def __str__(self):
        return self.__unicode__()

    def __unicode__(self):
        return self.name

    def __repr__(self):
        return "<Source('%s')>" % (self.name)

    def __iter__(self):
        keys = (
            'id name uri type language created last_seen seeds leechers size '
            'provider state state_name').split(' ')
        keys += [k for k in vars(self) if k[0] != '_']

        for k in set(keys):
            yield (k, getattr(self, k))

    def __lt__(self, other):
        return self.id.__lt__(other.id)

    def __eq__(self, other):
        return self.id.__eq__(other.id)

    def __hash__(self):
        return self.id.__hash__()

    def as_dict(self):
        return {k: v for (k, v) in self}

    @property
    def state_name(self):
        for attr in [x for x in dir(Source.State)]:
            if getattr(Source.State, attr) == self.state:
                return attr.lower()
        return "unknow-{}".format(self.state)

    @property
    def state_symbol(self):
        return self._SYMBOL_TABLE.get(self.state, ' ')

    @property
    def pretty_repr(self):
        return "[{icon}] {id} {name}".format(
            icon=self.state_symbol,
            id=self.id,
            name=self.name)


class Episode(Base):
    __tablename__ = 'episode'
    __table_args__ = (
        schema.UniqueConstraint('series', 'year', 'language', 'season',
                                'number'),
    )

    id = Column(Integer, primary_key=True)

    series = Column(String, nullable=False)
    _language = Column('language', String, nullable=True)
    year = Column(Integer, nullable=True)
    season = Column(Integer, nullable=False)
    # guessit returns episodeList attribute if more than one episode is
    # detected, take care of this
    number = Column(Integer, nullable=False)

    @hybrid_property
    def language(self):
        return self._language

    @language.setter
    def language(self, value):
        if not _check_language(value):
            raise ValueError(value)

        self._language = value

    def __str__(self):
        ret = '{series}{year} ({language}){season}{number}'
        ret = ret.format(
            series=self.series,
            year=' ({})'.format(self.year) if self.year else '',
            language=self.language or 'no region',
            season=', season {}'.format(self.season) if self.season else '',
            number=', episode {}'.format(self.number) if self.number else ''
        )

        return ret

    def __unicode__(self):
        return self.__str__()

    def __repr__(self):
        ret = self.series

        if self.year is not None:
            ret += ' (%04d)' % self.year

        ret += ' S%02d E%02d' % \
            (int(self.season or -1), int(self.number))

        return "<Episode ('%s')>" % ret

    def __iter__(self):
        keys = 'id series year language season number'.split(' ')
        for k in keys:
            yield (k, getattr(self, k))

    def as_dict(self):
        return {k: v for (k, v) in self}


class Movie(Base):
    __tablename__ = 'movie'
    __table_args__ = (
        schema.UniqueConstraint('title', 'language', 'year'),
    )

    id = Column(Integer, primary_key=True)

    title = Column(String, nullable=False)
    year = Column(Integer, nullable=True)
    _language = Column('language', String, nullable=True)

    @hybrid_property
    def language(self):
        return self._language

    @language.setter
    def language(self, value):
        if not _check_language(value):
            raise ValueError(value)

        self._language = value

    def __repr__(self):
        ret = self.title

        if self.year is not None:
            ret += ' (%04d)' % self.year

        return "<Movie ('%s')>" % ret

    def __str__(self):
        ret = '{title}{year} ({language})'
        ret = ret.format(
            title=self.title,
            year=' ({})'.format(self.year) if self.year else '',
            language=self.language or 'no region'
        )

        return ret

    def __unicode__(self):
        return self.__str__()

    def __iter__(self):
        keys = 'id title year language'.split(' ')
        for k in keys:
            yield (k, getattr(self, k))

    def as_dict(self):
        return {k: v for (k, v) in self}


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


def _check_language(lang):
    return (lang is None or re.match(r'^...(\-..)?$', lang))


def _check_type(typ):
    return typ in (None, 'movie', 'episode')
