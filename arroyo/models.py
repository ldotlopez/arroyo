# -*- coding: utf-8 -*-

import functools
import re
import sys


from appkit import (
    keyvaluestore,
    utils
)
from appkit.db import sqlalchemyutils as sautils
from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    and_,
    func,
    schema
)
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import (
    backref,
    relationship,
    validates
)


sautils.Base.metadata.naming_convention = {
  "ix": 'ix_%(column_0_label)s',
  "uq": "uq_%(table_name)s_%(column_0_name)s",
  "ck": "ck_%(table_name)s_%(constraint_name)s",
  "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
  "pk": "pk_%(table_name)s"
}


@functools.lru_cache(maxsize=8)
def _ensure_model_class(x):

    try:
        if issubclass(x, sautils.Base):
            return x
    except TypeError:
        pass

    if '.' in x:
        mod = sys.modules[x]
        x = x.split('.')[-1]

    else:
        mod = sys.modules[__name__]

    cls = getattr(mod, x)
    issubclass(cls, sautils.Base)

    return cls


# class _BaseModel:
#     REQUIRED_FIELDS = []
#     OPTIONAL_FIELDS = []

#     class Formats:
#         DEFAULT = '{classname} at 0x{hexid}'

#     def __iter__(self):
#         yield from (
#             self.__class__._REQUIRED_FIELDS +
#             self.__class__._OPTIONAL_FIELDS
#         )

#     def format(self, fmt=Formats.DEFAULT):
#         table = {
#             'classname': str(self.__class__),
#             'hexid': hex(id(self))
#         }
#         return fmt.format(**table)

#     def asdict(self):
#         return {
#             attr: getattr(self, attr)
#             for attr in self
#         }

#     def __eq__(self, other):
#         if not isinstance(other, self.__class__):
#             raise TypeError(other)

#         return self.id.__eq__(other.id)

#     def __lt__(self, other):
#         if not isinstance(other, self.__class__):
#             raise TypeError(other)

#         return self.id.__lt__(other.id)

#     def __repr__(self):
#         return '<' + self.format() + '>'

#     def __str__(self):
#         return self.__unicode__()


# class _EntityMixin:
#     REQUIRED_FIELDS = []
#     OPTIONAL_FIELDS = []

#     SELECTION_MODEL = None

#     @classmethod
#     def extract_relevant_data(cls, data):
#         pass

#     def is_confident(self):
#         raise NotImplementedError()

#     def is_complete(self):
#         raise NotImplementedError()


class EntityPropertyMixin:
    """Adds support for `entity` property
    Useful for Source and Selection

    Classes using this mixin should define the class attribute ENTITY_MAP:
    ENTITY_MAP = {
        # Related class (as string or as class): attribute
        'Episode': 'episode'
    }
    """

    ENTITY_MAP = {}

    @hybrid_property
    def entity(self):
        entity_attrs = self.ENTITY_MAP.values()

        for attr in entity_attrs:
            value = getattr(self, attr, None)
            if value:
                return value

        return None

    @entity.setter
    def entity(self, entity):
        m = {_ensure_model_class(k): v
             for (k, v) in self.ENTITY_MAP.items()}

        # Check for unknown entity type
        if entity is not None and entity.__class__ not in m:
            raise TypeError(entity)

        # Set all entity-attributes correctly
        for (model, attr) in m.items():
            value = entity if isinstance(entity, model) else None
            setattr(self, attr, value)


Variable = keyvaluestore.keyvaluemodel('Variable', sautils.Base, dict({
    '__doc__': "Define variables.",
    '__table_args__': (schema.UniqueConstraint('key'),)
    }))


SourceTag = keyvaluestore.keyvaluemodel(
    'SourceTag',
    sautils.Base,
    dict({
        '__doc__': "Define custom data attached to a source.",
        '__tablename__': 'sourcetag',
        '__table_args__': (schema.UniqueConstraint('source_id', 'key'),),
        'source_id': Column(Integer, ForeignKey('source.id',
                                                ondelete="CASCADE")),
        'source': relationship("Source",
                               backref=backref("tags",
                                               lazy='dynamic',
                                               cascade="all, delete, delete-orphan")),  # nopep8
    }))


class State:
    NONE = 0
    INITIALIZING = 1
    QUEUED = 2
    PAUSED = 3
    DOWNLOADING = 4
    SHARING = 5
    DONE = 6
    ARCHIVED = 7


class Source(EntityPropertyMixin, sautils.Base):
    class Formats:
        DEFAULT = '{name}'
        DETAIL = (
            "{name} "
            "(lang: {language}, size: {size}, ratio: {seeds}/{leechers})"
        )

    __tablename__ = 'source'

    _SYMBOL_TABLE = {
        State.INITIALIZING: '⋯',
        State.QUEUED: '⋯',
        State.PAUSED: '‖',
        State.DOWNLOADING: '↓',
        State.SHARING: '⇅',
        State.DONE: '✓',
        State.ARCHIVED: '▣'
    }

    ENTITY_MAP = {  # EntityPropertyMixin
        'Episode': 'episode',
        'Movie': 'movie'
    }

    # Required
    id = Column(Integer, primary_key=True)
    provider = Column(String, nullable=False)
    name = Column(String, nullable=False, index=True)
    created = Column(Integer, nullable=False)
    last_seen = Column(Integer, nullable=False)

    # Real ID
    urn = Column(String, nullable=True, unique=True, index=True)
    uri = Column(String, nullable=True, unique=True, index=True)

    # Other data
    size = Column(Integer, nullable=True)
    seeds = Column(Integer, nullable=True)
    leechers = Column(Integer, nullable=True)
    state = Column(Integer, nullable=False, default=State.NONE)

    type = Column(String, nullable=True)
    language = Column(String, nullable=True)

    # EntitySupport
    episode_id = Column(Integer,
                        ForeignKey('episode.id', ondelete="SET NULL"),
                        nullable=True)
    episode = relationship('Episode',
                           uselist=False,
                           backref=backref("sources", lazy='dynamic'))

    movie_id = Column(Integer,
                      ForeignKey('movie.id', ondelete="SET NULL"),
                      nullable=True)
    movie = relationship('Movie',
                         uselist=False,
                         backref=backref("sources", lazy='dynamic'))

    @property
    def tag_dict(self):
        return {x.key: x.value for x in self.tags.all()}

    @hybrid_property
    def _discriminator(self):
        return self.urn or self.uri

    @_discriminator.expression
    def _discriminator(self):
        return func.coalesce(self.urn, self.uri)

    @hybrid_property
    def age(self):
        return utils.now_timestamp() - self.created

    @hybrid_property
    def needs_postprocessing(self):
        return self.urn is None and self.uri is not None

    @needs_postprocessing.expression
    def needs_postprocessing(self):
        return and_(self.urn.is_(None), ~self.uri.is_(None))

    @hybrid_property
    def share_ratio(self):
        seeds = self.seeds if self.seeds is not None else 0
        leechers = self.leechers if self.leechers is not None else 0

        if not self.seeds and not self.leechers:
            return None

        if seeds and leechers == 0:
            return float(sys.maxsize)

        if seeds == 0 and leechers:
            return 0.0

        return seeds / leechers

    @property
    def state_name(self):
        for attr in [x for x in dir(State)]:
            if getattr(State, attr) == self.state:
                return attr.lower()
        return "unknow-{}".format(self.state)

    @property
    def state_symbol(self):
        return self._SYMBOL_TABLE.get(self.state, ' ')

    @classmethod
    def normalize(cls, key, value):
        if key in ['name', 'provider', 'urn', 'uri']:
            value = str(value)
            if not value:
                raise ValueError(value)

            return value

        elif key in ['created', 'last_seen']:
            return int(value)

        elif key in ['size', 'seeds', 'leechers']:
            if value is None:
                return None

            return int(key)

        elif key == 'language':
            if value is None:
                return None

            value = str(value)

            if not re.match(r'^...(\-..)?$', value):
                raise ValueError(value)

            return value

        elif key == 'type':
            if value is None:
                return None

            value = str(value)

            if value in (
                    'application',
                    'book',
                    'episode',
                    'game',
                    'movie',
                    'music',
                    'other',
                    'xxx'):
                return value

            raise ValueError(value)

        else:
            raise Exception(key)

    @validates('language', 'type')
    def validate(self, key, value):
        if (key == 'urn' and self.uri or
                key == 'uri' and self.urn):
            raise ValueError(value)

        return self.normalize(key, value)

    def asdict(self):
        ret = {
            attr: getattr(self, attr)
            for attr in self
            if attr != 'tags'
        }
        ret['tags'] = self.tag_dict

        return ret

    def format(self, fmt=Formats.DEFAULT, extra_data={}):
        data = self.asdict()
        data['seeds'] = data.get('seeds') or '-'
        data['leechers'] = data.get('leechers') or '-'
        data['language'] = data.get('language') or 'unknow'

        data.update(extra_data)

        return fmt.format(**data)

    def __eq__(self, other):
        return self.id.__eq__(other.id)

    def __lt__(self, other):
        return self.id.__lt__(other.id)

    # FIXME: Delete this method
    def __hash__(self):
        return hash((self.id, self.urn, self.uri))

    def __iter__(self):
        yield from [
            'age', 'created', 'entity', 'episode', 'episode_id', 'id',
            'language', 'last_seen', 'leechers', 'movie', 'movie_id', 'name',
            'provider', 'seeds', 'share_ratio', 'size', 'state',
            'state_symbol', 'tags', 'type', 'type', 'uri', 'urn'
        ]

    def __str__(self):
        return self.__unicode__()

    def __repr__(self):
        return "<Source {id} ('{name}')>".format(
            id=self.id,
            name=self.name)

    def __unicode__(self):
        return self.format(self.Formats.DEFAULT)


class Selection(EntityPropertyMixin, sautils.Base):
    __tablename__ = 'selection'
    ENTITY_MAP = {
        'Episode': 'episode',
        'Movie': 'movie'
    }

    id = Column(Integer, primary_key=True)
    type = Column(String(50))

    source_id = Column(Integer, ForeignKey('source.id', ondelete="CASCADE"),
                       nullable=False)
    source = relationship('Source')

    __mapper_args__ = {
        'polymorphic_on': 'type'
    }


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
            episode=repr(self.episode),
            source=repr(self.source))


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
            movie=repr(self.movie),
            source=repr(self.source))


class Episode(sautils.Base):
    __tablename__ = 'episode'
    __table_args__ = (
        schema.UniqueConstraint('series', 'year', 'season', 'number'),
    )

    id = Column(Integer, primary_key=True)

    series = Column(String, nullable=False, index=True)
    year = Column(Integer, nullable=True)
    season = Column(Integer, nullable=False)
    # FIXME: guessit returns episodeList attribute if more than one episode is
    # detected, take care of this
    number = Column(Integer, nullable=False)

    SELECTION_MODEL = EpisodeSelection

    class Formats:
        DEFAULT = '{series_with_year} s{season:02d} e{number:02d}'

    @classmethod
    def normalize(cls, key, value):

        # Nullables
        if key == 'year' and value is None:
            return None

        # Normalization
        if key == 'series':
            value = value.lower()
            if not value:
                raise ValueError(value)

        elif key in ['season', 'number', 'year']:
            value = int(value)
            if value < 0:
                raise ValueError(value)

        else:
            ValueError(repr(key) + '=' + repr(value))

        return value

    @validates('series', 'year', 'season', 'number')
    def validate(self, key, value):
        return self.normalize(key, value)

    def asdict(self):
        return {
            attr: getattr(self, attr)
            for attr in self
        }

    def format(self, fmt=Formats.DEFAULT, extra_data={}):
        d = self.asdict()

        if self.year:
            series_with_year = "{series} ({year})"
        else:
            series_with_year = "{series}"

        d['series_with_year'] = series_with_year.format(**d)
        d.update(**extra_data)

        return fmt.format(**d)

    def __iter__(self):
        yield from ['id', 'series', 'year', 'season', 'number']

    def __repr__(self):
        return "<Episode #{id} {fmt}>".format(
            id=self.id or '??',
            fmt=self.format())

    def __str__(self):
        return self.__unicode__()

    def __unicode__(self):
        return self.format()


class Movie(sautils.Base):
    __tablename__ = 'movie'
    __table_args__ = (
        schema.UniqueConstraint('title', 'year'),
    )

    id = Column(Integer, primary_key=True)

    title = Column(String, nullable=False, index=True)
    year = Column(Integer, nullable=True)

    SELECTION_MODEL = MovieSelection

    class Formats:
        DEFAULT = '{title_with_year}'

    @classmethod
    def normalize(cls, key, value):
        # Nullables
        if key == 'year' and value is None:
            return None

        # Real normalization
        if key == 'title':
            value = value.lower()
            if not value:
                raise ValueError(value)

        elif key == 'year':
            value = int(value)
            if value < 0:
                raise ValueError(value)

        else:
            ValueError(repr(key) + '=' + repr(value))

        return value

    @validates('title', 'year')
    def validate(self, key, value):
        return self.normalize(key, value)

    def asdict(self):
        return {
            attr: getattr(self, attr)
            for attr in self
        }

    def format(self, fmt=Formats.DEFAULT, extra_data={}):
        d = self.asdict()

        if self.year:
            title_with_year = "{title} ({year})"
        else:
            title_with_year = "{title}"

        d['title_with_year'] = title_with_year.format(**d)
        d.update(**extra_data)

        return fmt.format(**d)

    def __iter__(self):
        yield from ['id', 'title', 'year']

    def __repr__(self):
        return "<Movie #{id} {fmt}>".format(
            id=self.id or '??',
            fmt=self.format())

    def __str__(self):
        return self.__unicode__()

    def __unicode__(self):
        return self.format()
