# -*- coding: utf-8 -*-
# [SublimeLinter pep8-max-line-length:119]
# vim: set fileencoding=utf-8 :

# import json
import random
import re
from urllib import parse

from ldotcommons.sqlalchemy import Base
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy import schema
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property

from ldotcommons import logging, utils


_logger = logging.get_logger('models')


class Source(Base):
    __tablename__ = 'source'

    class State:
        NONE = 0
        INITIALIZING = 1
        PAUSED = 2
        DOWNLOADING = 3
        SHARING = 4
        DONE = 5
        ARCHIVED = 6

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    uri = Column(String, nullable=False, unique=True)
    timestamp = Column(Integer, nullable=False)
    size = Column(Integer, nullable=True)
    provider = Column(String, nullable=False)

    seeds = Column(Integer, nullable=True)
    leechers = Column(Integer, nullable=True)
    state = Column(Integer, nullable=False, default=State.NONE)

    _type = Column('type', String, nullable=True)
    _language = Column('language', String, nullable=True)

    episode_id = Column(Integer, ForeignKey('episode.id'), nullable=True)
    movie_id = Column(Integer, ForeignKey('movie.id'), nullable=True)

    # json encoded media data
    # _mediadata = Column('mediadata', String, nullable=True)

    # Type property
    @hybrid_property
    def type(self):
        return self._type

    @type.setter
    def type(self, value):
        if not _check_type(value):
            raise ValueError(value)

        self._type = value

    # Language property
    @hybrid_property
    def language(self):
        return self._language

    @language.setter
    def language(self, value):
        if not _check_language(value):
            raise ValueError(value)

        self._language = value

    def __str__(self):
        return self.__unicode__()

    def __unicode__(self):
        return self.name

    def __repr__(self):
        return "<Source('%s')>" % (self.name)

    def __iter__(self):
        keys = (
            'id name uri type language timestamp seeds leechers size provider '
            'state state_name').split(' ')
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

    # @property
    # def mediadata(self):
    #     return json.loads(self._mediadata)

    # @mediadata.setter
    # def mediadata(self, value):
    #     self._mediadata = json.dumps(value)


class Episode(Base):
    __tablename__ = 'episode'
    __table_args__ = (
        schema.UniqueConstraint('series', 'year', 'language', 'season',
                                'number'),
    )

    id = Column(Integer, primary_key=True)
    sources = relationship("Source")

    series = Column(String, nullable=False)
    _language = Column('language', String, nullable=True)
    year = Column(Integer, nullable=True)

    season = Column(String, nullable=False)
    # guessit returns episodeList attribute if more than one episode is
    # detected, take care of this
    number = Column(String, nullable=False)

    sources = relationship("Source", backref="episode")

    @hybrid_property
    def language(self):
        return self._language

    @language.setter
    def language(self, value):
        if not _check_language(value):
            raise ValueError(value)

        self._language = value

    def __repr__(self):
        ret = self.series

        if self.year is not None:
            ret += ' (%04d)' % self.year

        ret += ' S%02d E%02d' % \
            (int(self.season or -1), int(self.number))

        return "<Episode ('%s')>" % ret


class Movie(Base):
    __tablename__ = 'movie'
    __table_args__ = (
        schema.UniqueConstraint('title', 'language', 'year'),
    )

    id = Column(Integer, primary_key=True)
    sources = relationship("Source", backref="movie")

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
        ret = self.name

        if self.year is not None:
            ret += ' (%04d)' % self.year

        return "<Movie ('%s')>" % ret


def _check_language(lang):
    return (lang is None or re.match(r'^...(\-..)?$', lang))


def _check_type(typ):
    return typ in (None, 'movie', 'episode')


def source_data_builder(**opts):
    trackers = [
        'udp://foo.yellow.com:80',
        'udp://bar.red.com:80',
        'udp://one.blue.it:6969',
        'udp://two.green.de:80',
        'udp://three.red.com:1337']

    idstr = 'urn:btih:' + ''.join([
        random.choice('0123456789abcdef') for x in range(40)
    ])
    ntrackers = random.randint(1, len(trackers))
    randtrackers = random.sample(trackers, ntrackers)

    name = opts['name']
    query = {
        'dn': [name],
        'tr': randtrackers,
    }
    source = {
        'id': idstr,
        'name': name,
        'uri': 'magnet:?xt={}&{}'.format(
            idstr, parse.urlencode(query, doseq=True)
        ),
        'timestamp': utils.utcnow_timestamp(),
        'provider': 'test-provider'
    }
    extra = {x: opts.get(x, None) for x in [
        'type', 'language', 'seeds', 'leechers', 'size', 'provider'
    ]}
    extra = {k: v for (k, v) in extra.items() if v is not None}
    source.update(extra)

    return source


def source_fixture_loader(fixture):
    return Source(**source_data_builder(**fixture))
