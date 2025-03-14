"""Add ref stats

Revision ID: dcb2ba88f1dd
Revises: b3ccc8ac2eeb
Create Date: 2024-12-22 16:06:03.391501

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'dcb2ba88f1dd'
down_revision = 'b3ccc8ac2eeb'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('org_stats_referee',
    sa.Column('org_id', sa.Integer(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('human_id', sa.Integer(), nullable=False),
    sa.Column('games_reffed', sa.Integer(), nullable=True),
    sa.Column('penalties_given', sa.Integer(), nullable=True),
    sa.Column('penalties_per_game', sa.Float(), nullable=True),
    sa.Column('gm_given', sa.Integer(), nullable=True),
    sa.Column('gm_per_game', sa.Float(), nullable=True),
    sa.ForeignKeyConstraint(['human_id'], ['humans.id'], ),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('human_id', 'org_id', name='_human_org_uc_referee1')
    )
    with op.batch_alter_table('org_stats_referee', schema=None) as batch_op:
        batch_op.create_index('idx_org_games_reffed1', ['org_id', 'games_reffed'], unique=False)
        batch_op.create_index('idx_org_gm_given1', ['org_id', 'gm_given'], unique=False)
        batch_op.create_index('idx_org_gm_per_game1', ['org_id', 'gm_per_game'], unique=False)
        batch_op.create_index('idx_org_penalties_given1', ['org_id', 'penalties_given'], unique=False)
        batch_op.create_index('idx_org_penalties_per_game1', ['org_id', 'penalties_per_game'], unique=False)

    op.create_table('division_stats_referee',
    sa.Column('division_id', sa.Integer(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('human_id', sa.Integer(), nullable=False),
    sa.Column('games_reffed', sa.Integer(), nullable=True),
    sa.Column('penalties_given', sa.Integer(), nullable=True),
    sa.Column('penalties_per_game', sa.Float(), nullable=True),
    sa.Column('gm_given', sa.Integer(), nullable=True),
    sa.Column('gm_per_game', sa.Float(), nullable=True),
    sa.ForeignKeyConstraint(['division_id'], ['divisions.id'], ),
    sa.ForeignKeyConstraint(['human_id'], ['humans.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('human_id', 'division_id', name='_human_division_uc_referee1')
    )
    with op.batch_alter_table('division_stats_referee', schema=None) as batch_op:
        batch_op.create_index('idx_division_games_reffed1', ['division_id', 'games_reffed'], unique=False)
        batch_op.create_index('idx_division_gm_given1', ['division_id', 'gm_given'], unique=False)
        batch_op.create_index('idx_division_gm_per_game1', ['division_id', 'gm_per_game'], unique=False)
        batch_op.create_index('idx_division_penalties_given1', ['division_id', 'penalties_given'], unique=False)
        batch_op.create_index('idx_division_penalties_per_game1', ['division_id', 'penalties_per_game'], unique=False)

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('division_stats_referee', schema=None) as batch_op:
        batch_op.drop_index('idx_division_penalties_per_game1')
        batch_op.drop_index('idx_division_penalties_given1')
        batch_op.drop_index('idx_division_gm_per_game1')
        batch_op.drop_index('idx_division_gm_given1')
        batch_op.drop_index('idx_division_games_reffed1')

    op.drop_table('division_stats_referee')
    with op.batch_alter_table('org_stats_referee', schema=None) as batch_op:
        batch_op.drop_index('idx_org_penalties_per_game1')
        batch_op.drop_index('idx_org_penalties_given1')
        batch_op.drop_index('idx_org_gm_per_game1')
        batch_op.drop_index('idx_org_gm_given1')
        batch_op.drop_index('idx_org_games_reffed1')

    op.drop_table('org_stats_referee')
    # ### end Alembic commands ###
