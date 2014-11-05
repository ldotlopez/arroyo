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
    #                       uselist=False,
    #                       backref=backref("selection", uselist=False))
    # __mapper_args__ = {
    #     'polymorphic_identity': 'episode',
    #     'polymorphic_on': type
    # }


class EpisodeSelection(Selection):
    episode_id = Column(Integer, ForeignKey('episode.id', ondelete="CASCADE"),
                        nullable=True)
    episode = relationship("Episode",
                           backref=backref("selection", uselist=False, cascade="all, delete"))

    __mapper_args__ = {
        'polymorphic_identity': 'episode'
    }

sess = create_session('sqlite:///:memory:')
for i in 'a b c d'.split():
    src = Source(name='source '+i)
    ep = Episode(name='episode '+i)
    sess.add(ep)
    sess.add(src)
    sess.commit()

    sel = EpisodeSelection(episode_id=ep.id, source_id=src.id)
    # ep.sources.append(src)
    sess.add(sel)

sess.commit()

# Delete some selection
print("-")
print("sources:", sess.query(Source).count())
print("episodes:", sess.query(Episode).count())
sess.delete(sess.query(EpisodeSelection).first())
print("sources:", sess.query(Source).count())
print("episodes:", sess.query(Episode).count())

# Delete source
print("-")
print("selections:", sess.query(EpisodeSelection).count())
src_id = sess.query(EpisodeSelection).first().source_id
sess.delete(sess.query(Source).filter_by(id=src_id).one())
sess.commit()
print("selections:", sess.query(EpisodeSelection).count())


# Delete episode
print("-")
print("selections:", sess.query(EpisodeSelection).count())
ep_id = sess.query(EpisodeSelection).first().source_id
sess.delete(sess.query(Episode).filter_by(id=ep_id).one())
sess.commit()
print("selections:", sess.query(EpisodeSelection).count())
