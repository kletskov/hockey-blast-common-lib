"""Add Skater stats per level

Revision ID: 1c368bfe6622
Revises: 3bc694f30253
Create Date: 2025-01-29 17:15:30.901640

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1c368bfe6622'
down_revision = '3bc694f30253'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('level_stats_skater',
    sa.Column('level_id', sa.Integer(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('human_id', sa.Integer(), nullable=False),
    sa.Column('games_played', sa.Integer(), nullable=True),
    sa.Column('games_played_rank', sa.Integer(), nullable=True),
    sa.Column('goals', sa.Integer(), nullable=True),
    sa.Column('goals_rank', sa.Integer(), nullable=True),
    sa.Column('assists', sa.Integer(), nullable=True),
    sa.Column('assists_rank', sa.Integer(), nullable=True),
    sa.Column('points', sa.Integer(), nullable=True),
    sa.Column('points_rank', sa.Integer(), nullable=True),
    sa.Column('penalties', sa.Integer(), nullable=True),
    sa.Column('penalties_rank', sa.Integer(), nullable=True),
    sa.Column('goals_per_game', sa.Float(), nullable=True),
    sa.Column('goals_per_game_rank', sa.Integer(), nullable=True),
    sa.Column('points_per_game', sa.Float(), nullable=True),
    sa.Column('points_per_game_rank', sa.Integer(), nullable=True),
    sa.Column('assists_per_game', sa.Float(), nullable=True),
    sa.Column('assists_per_game_rank', sa.Integer(), nullable=True),
    sa.Column('penalties_per_game', sa.Float(), nullable=True),
    sa.Column('penalties_per_game_rank', sa.Integer(), nullable=True),
    sa.Column('total_in_rank', sa.Integer(), nullable=True),
    sa.Column('first_game_id', sa.Integer(), nullable=True),
    sa.Column('last_game_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['first_game_id'], ['games.id'], ),
    sa.ForeignKeyConstraint(['human_id'], ['humans.id'], ),
    sa.ForeignKeyConstraint(['last_game_id'], ['games.id'], ),
    sa.ForeignKeyConstraint(['level_id'], ['levels.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('human_id', 'level_id', name='_human_level_uc_skater1')
    )
    with op.batch_alter_table('level_stats_skater', schema=None) as batch_op:
        batch_op.create_index('idx_level_assists_per_game3', ['level_id', 'assists_per_game'], unique=False)
        batch_op.create_index('idx_level_games_played3', ['level_id', 'games_played'], unique=False)
        batch_op.create_index('idx_level_goals_per_game3', ['level_id', 'goals_per_game'], unique=False)
        batch_op.create_index('idx_level_penalties_per_game3', ['level_id', 'penalties_per_game'], unique=False)
        batch_op.create_index('idx_level_points_per_game3', ['level_id', 'points_per_game'], unique=False)

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('level_stats_skater', schema=None) as batch_op:
        batch_op.drop_index('idx_level_points_per_game3')
        batch_op.drop_index('idx_level_penalties_per_game3')
        batch_op.drop_index('idx_level_goals_per_game3')
        batch_op.drop_index('idx_level_games_played3')
        batch_op.drop_index('idx_level_assists_per_game3')

    op.drop_table('level_stats_skater')
    # ### end Alembic commands ###
