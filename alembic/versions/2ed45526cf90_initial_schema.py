"""Initial schema

Revision ID: 2ed45526cf90
Revises: 
Create Date: 2017-07-21 14:52:48.114790

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2ed45526cf90'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('episode',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('series', sa.String(), nullable=False),
    sa.Column('year', sa.Integer(), nullable=True),
    sa.Column('season', sa.Integer(), nullable=False),
    sa.Column('number', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_episode')),
    sa.UniqueConstraint('series', 'year', 'season', 'number', name=op.f('uq_episode_series'))
    )
    op.create_index(op.f('ix_episode_series'), 'episode', ['series'], unique=False)
    op.create_table('movie',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(), nullable=False),
    sa.Column('year', sa.Integer(), nullable=True),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_movie')),
    sa.UniqueConstraint('title', 'year', name=op.f('uq_movie_title'))
    )
    op.create_index(op.f('ix_movie_title'), 'movie', ['title'], unique=False)
    op.create_table('variable',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('key', sa.String(), nullable=False),
    sa.Column('value', sa.String(), nullable=True),
    sa.Column('type', sa.String(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_variable')),
    sa.UniqueConstraint('key', name=op.f('uq_variable_key'))
    )
    op.create_table('source',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('provider', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('created', sa.Integer(), nullable=False),
    sa.Column('last_seen', sa.Integer(), nullable=False),
    sa.Column('urn', sa.String(), nullable=True),
    sa.Column('uri', sa.String(), nullable=True),
    sa.Column('size', sa.Integer(), nullable=True),
    sa.Column('seeds', sa.Integer(), nullable=True),
    sa.Column('leechers', sa.Integer(), nullable=True),
    sa.Column('type', sa.String(), nullable=True),
    sa.Column('language', sa.String(), nullable=True),
    sa.Column('episode_id', sa.Integer(), nullable=True),
    sa.Column('movie_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['episode_id'], ['episode.id'], name=op.f('fk_source_episode_id_episode'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['movie_id'], ['movie.id'], name=op.f('fk_source_movie_id_movie'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_source'))
    )
    op.create_index(op.f('ix_source_name'), 'source', ['name'], unique=False)
    op.create_index(op.f('ix_source_uri'), 'source', ['uri'], unique=True)
    op.create_index(op.f('ix_source_urn'), 'source', ['urn'], unique=True)
    op.create_table('download',
    sa.Column('source_id', sa.Integer(), nullable=False),
    sa.Column('foreign_id', sa.String(), nullable=False),
    sa.Column('state', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['source_id'], ['source.id'], name=op.f('fk_download_source_id_source'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('source_id', name=op.f('pk_download')),
    sa.UniqueConstraint('foreign_id', name=op.f('uq_download_foreign_id'))
    )
    op.create_table('selection',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('type', sa.String(length=50), nullable=True),
    sa.Column('source_id', sa.Integer(), nullable=False),
    sa.Column('episode_id', sa.Integer(), nullable=True),
    sa.Column('movie_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['episode_id'], ['episode.id'], name=op.f('fk_selection_episode_id_episode'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['movie_id'], ['movie.id'], name=op.f('fk_selection_movie_id_movie'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['source_id'], ['source.id'], name=op.f('fk_selection_source_id_source'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_selection'))
    )
    op.create_table('sourcetag',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('key', sa.String(), nullable=False),
    sa.Column('value', sa.String(), nullable=True),
    sa.Column('type', sa.String(), nullable=False),
    sa.Column('source_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['source_id'], ['source.id'], name=op.f('fk_sourcetag_source_id_source'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_sourcetag')),
    sa.UniqueConstraint('source_id', 'key', name=op.f('uq_sourcetag_source_id'))
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('sourcetag')
    op.drop_table('selection')
    op.drop_table('download')
    op.drop_index(op.f('ix_source_urn'), table_name='source')
    op.drop_index(op.f('ix_source_uri'), table_name='source')
    op.drop_index(op.f('ix_source_name'), table_name='source')
    op.drop_table('source')
    op.drop_table('variable')
    op.drop_index(op.f('ix_movie_title'), table_name='movie')
    op.drop_table('movie')
    op.drop_index(op.f('ix_episode_series'), table_name='episode')
    op.drop_table('episode')
    # ### end Alembic commands ###
