from ldotcommons.sqlalchemy import create_session, Base
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship, backref


class Source(Base):
    __tablename__ = 'source'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)

    episode_id = Column(Integer, ForeignKey('episode.id', ondelete="SET NULL"),
                        nullable=True)
    episode = relationship("Episode",
                           uselist=False,
                           backref="sources")

    def __repr__(self):
        return self.name


class Episode(Base):
    __tablename__ = 'episode'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)

    def __repr__(self):
        return self.name


class Selection(Base):
    __tablename__ = 'selection'

    id = Column(Integer, primary_key=True)
    type = Column(String(50))

    source_id = Column(Integer, ForeignKey('source.id', ondelete="CASCADE"),
                       nullable=False)
    source = relationship("Source")

    __mapper_args__ = {
        'polymorphic_identity': 'episode',
        'polymorphic_on': type
    }


class EpisodeSelection(Selection):
    # single_parent=True,
    # cascade="all, delete, delete-orphan")
    episode_id = Column(Integer, ForeignKey('episode.id', ondelete="CASCADE"),
                        nullable=False)
    episode = relationship("Episode",
                           uselist=False,
                           backref=backref("selection", uselist=False))

    __mapper_args__ = {
        'polymorphic_identity': 'episode'
    }

sess = create_session('sqlite:///:memory:')
for i in 'a b c d'.split():
    src = Source(name='source '+i)
    ep = Episode(name='episode '+i)

    sel = EpisodeSelection(episode=ep, source=src)
    ep.sources.append(src)
    sess.add(ep)
    sess.add(sel)
sess.commit()

# Delete source
print("selections:", sess.query(Selection).count())
sess.delete(sess.query(Selection).first().source)
sess.commit()
print("selections:", sess.query(Selection).count())


# Delete episode
print("selections:", sess.query(Selection).count())
sess.delete(sess.query(Selection).first().episode)
sess.commit()  # Exception here: sqlalchemy.exc.IntegrityError: (IntegrityError) NOT NULL constraint failed: selection.episode_id 'UPDATE selection SET episode_id=? WHERE selection.id = ?' (None, 2)
print("selections:", sess.query(Selection).count())
