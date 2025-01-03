"""Base class for human stats, modify DivisionStatsHuman

Revision ID: 8386a3554f0f
Revises: f7f0e953759c
Create Date: 2024-12-22 15:45:22.700478

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8386a3554f0f'
down_revision = 'f7f0e953759c'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('division_stats_human', schema=None) as batch_op:
        batch_op.add_column(sa.Column('games_total', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('games_skater', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('games_referee', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('games_scorekeeper', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('games_goalie', sa.Integer(), nullable=True))
        batch_op.drop_constraint('_human_division_uc1', type_='unique')
        batch_op.drop_index('idx_division_assists_per_game1')
        batch_op.drop_index('idx_division_games_played1')
        batch_op.drop_index('idx_division_goals_per_game1')
        batch_op.drop_index('idx_division_penalties_per_game1')
        batch_op.drop_index('idx_division_points_per_game1')
        batch_op.create_unique_constraint('_human_division_stats_uc1', ['human_id', 'division_id'])
        batch_op.create_index('idx_division_games_goalie1', ['division_id', 'games_goalie'], unique=False)
        batch_op.create_index('idx_division_games_referee1', ['division_id', 'games_referee'], unique=False)
        batch_op.create_index('idx_division_games_scorekeeper1', ['division_id', 'games_scorekeeper'], unique=False)
        batch_op.create_index('idx_division_games_skater1', ['division_id', 'games_skater'], unique=False)
        batch_op.create_index('idx_division_games_total1', ['division_id', 'games_total'], unique=False)
        batch_op.drop_column('penalties_per_game')
        batch_op.drop_column('assists_per_game')
        batch_op.drop_column('games_played')
        batch_op.drop_column('goals')
        batch_op.drop_column('points')
        batch_op.drop_column('goals_per_game')
        batch_op.drop_column('penalties')
        batch_op.drop_column('points_per_game')
        batch_op.drop_column('assists')

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('division_stats_human', schema=None) as batch_op:
        batch_op.add_column(sa.Column('assists', sa.INTEGER(), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('points_per_game', sa.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('penalties', sa.INTEGER(), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('goals_per_game', sa.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('points', sa.INTEGER(), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('goals', sa.INTEGER(), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('games_played', sa.INTEGER(), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('assists_per_game', sa.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('penalties_per_game', sa.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=True))
        batch_op.drop_index('idx_division_games_total1')
        batch_op.drop_index('idx_division_games_skater1')
        batch_op.drop_index('idx_division_games_scorekeeper1')
        batch_op.drop_index('idx_division_games_referee1')
        batch_op.drop_index('idx_division_games_goalie1')
        batch_op.drop_constraint('_human_division_stats_uc1', type_='unique')
        batch_op.create_index('idx_division_points_per_game1', ['division_id', 'points_per_game'], unique=False)
        batch_op.create_index('idx_division_penalties_per_game1', ['division_id', 'penalties_per_game'], unique=False)
        batch_op.create_index('idx_division_goals_per_game1', ['division_id', 'goals_per_game'], unique=False)
        batch_op.create_index('idx_division_games_played1', ['division_id', 'games_played'], unique=False)
        batch_op.create_index('idx_division_assists_per_game1', ['division_id', 'assists_per_game'], unique=False)
        batch_op.create_unique_constraint('_human_division_uc1', ['human_id', 'division_id'])
        batch_op.drop_column('games_goalie')
        batch_op.drop_column('games_scorekeeper')
        batch_op.drop_column('games_referee')
        batch_op.drop_column('games_skater')
        batch_op.drop_column('games_total')

    # ### end Alembic commands ###
