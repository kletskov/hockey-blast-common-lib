"""Add division_team_standings table

Revision ID: a1b2c3d4e5f6
Revises: 
Create Date: 2026-03-25
"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = '260a865a44c7'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'division_team_standings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('division_id', sa.Integer(), sa.ForeignKey('divisions.id'), nullable=False, index=True),
        sa.Column('team_id', sa.Integer(), sa.ForeignKey('teams.id'), nullable=False, index=True),
        sa.Column('games_played', sa.Integer(), nullable=False, default=0),
        sa.Column('wins', sa.Integer(), nullable=False, default=0),
        sa.Column('losses', sa.Integer(), nullable=False, default=0),
        sa.Column('ties', sa.Integer(), nullable=False, default=0),
        sa.Column('ot_wins', sa.Integer(), nullable=False, default=0),
        sa.Column('ot_losses', sa.Integer(), nullable=False, default=0),
        sa.Column('points', sa.Integer(), nullable=False, default=0),
        sa.Column('goals_for', sa.Integer(), nullable=False, default=0),
        sa.Column('goals_against', sa.Integer(), nullable=False, default=0),
        sa.Column('goal_differential', sa.Integer(), nullable=False, default=0),
        sa.Column('rank', sa.Integer(), nullable=True),
        sa.Column('is_champion', sa.Boolean(), nullable=False, default=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.UniqueConstraint('division_id', 'team_id', name='uq_division_team_standings'),
    )
    op.create_index('idx_div_team_standings_div', 'division_team_standings', ['division_id'])
    op.create_index('idx_div_team_standings_team', 'division_team_standings', ['team_id'])


def downgrade():
    op.drop_table('division_team_standings')
