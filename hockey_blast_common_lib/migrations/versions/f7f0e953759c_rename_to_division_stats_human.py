"""rename to division_stats_human

Revision ID: f7f0e953759c
Revises: d0754f1837ac
Create Date: 2024-12-22 15:34:55.795795

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f7f0e953759c'
down_revision = 'd0754f1837ac'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('division_stats_human',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('human_id', sa.Integer(), nullable=False),
    sa.Column('division_id', sa.Integer(), nullable=False),
    sa.Column('games_played', sa.Integer(), nullable=True),
    sa.Column('goals', sa.Integer(), nullable=True),
    sa.Column('assists', sa.Integer(), nullable=True),
    sa.Column('points', sa.Integer(), nullable=True),
    sa.Column('penalties', sa.Integer(), nullable=True),
    sa.Column('goals_per_game', sa.Float(), nullable=True),
    sa.Column('points_per_game', sa.Float(), nullable=True),
    sa.Column('assists_per_game', sa.Float(), nullable=True),
    sa.Column('penalties_per_game', sa.Float(), nullable=True),
    sa.ForeignKeyConstraint(['division_id'], ['divisions.id'], ),
    sa.ForeignKeyConstraint(['human_id'], ['humans.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('human_id', 'division_id', name='_human_division_uc1')
    )
    with op.batch_alter_table('division_stats_human', schema=None) as batch_op:
        batch_op.create_index('idx_division_assists_per_game1', ['division_id', 'assists_per_game'], unique=False)
        batch_op.create_index('idx_division_games_played1', ['division_id', 'games_played'], unique=False)
        batch_op.create_index('idx_division_goals_per_game1', ['division_id', 'goals_per_game'], unique=False)
        batch_op.create_index('idx_division_penalties_per_game1', ['division_id', 'penalties_per_game'], unique=False)
        batch_op.create_index('idx_division_points_per_game1', ['division_id', 'points_per_game'], unique=False)

    with op.batch_alter_table('human_division_stats', schema=None) as batch_op:
        batch_op.drop_index('idx_division_assists_per_game')
        batch_op.drop_index('idx_division_games_played')
        batch_op.drop_index('idx_division_goals_per_game')
        batch_op.drop_index('idx_division_penalties_per_game')
        batch_op.drop_index('idx_division_points_per_game')

    op.drop_table('human_division_stats')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('human_division_stats',
    sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
    sa.Column('human_id', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.Column('division_id', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.Column('games_played', sa.INTEGER(), autoincrement=False, nullable=True),
    sa.Column('goals', sa.INTEGER(), autoincrement=False, nullable=True),
    sa.Column('assists', sa.INTEGER(), autoincrement=False, nullable=True),
    sa.Column('points', sa.INTEGER(), autoincrement=False, nullable=True),
    sa.Column('goals_per_game', sa.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=True),
    sa.Column('points_per_game', sa.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=True),
    sa.Column('assists_per_game', sa.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=True),
    sa.Column('penalties', sa.INTEGER(), autoincrement=False, nullable=True),
    sa.Column('penalties_per_game', sa.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['division_id'], ['divisions.id'], name='human_division_stats_division_id_fkey'),
    sa.ForeignKeyConstraint(['human_id'], ['humans.id'], name='human_division_stats_human_id_fkey'),
    sa.PrimaryKeyConstraint('id', name='human_division_stats_pkey'),
    sa.UniqueConstraint('human_id', 'division_id', name='_human_division_uc')
    )
    with op.batch_alter_table('human_division_stats', schema=None) as batch_op:
        batch_op.create_index('idx_division_points_per_game', ['division_id', 'points_per_game'], unique=False)
        batch_op.create_index('idx_division_penalties_per_game', ['division_id', 'penalties_per_game'], unique=False)
        batch_op.create_index('idx_division_goals_per_game', ['division_id', 'goals_per_game'], unique=False)
        batch_op.create_index('idx_division_games_played', ['division_id', 'games_played'], unique=False)
        batch_op.create_index('idx_division_assists_per_game', ['division_id', 'assists_per_game'], unique=False)

    with op.batch_alter_table('division_stats_human', schema=None) as batch_op:
        batch_op.drop_index('idx_division_points_per_game1')
        batch_op.drop_index('idx_division_penalties_per_game1')
        batch_op.drop_index('idx_division_goals_per_game1')
        batch_op.drop_index('idx_division_games_played1')
        batch_op.drop_index('idx_division_assists_per_game1')

    op.drop_table('division_stats_human')
    # ### end Alembic commands ###
