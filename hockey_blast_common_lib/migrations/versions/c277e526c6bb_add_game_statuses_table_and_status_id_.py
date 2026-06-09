"""Add game_statuses table and status_id to games

Revision ID: c277e526c6bb
Revises: 7bb61ab19ff0
Create Date: 2026-06-05 15:07:54.407507

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c277e526c6bb'
down_revision = '7bb61ab19ff0'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('game_statuses',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=50), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.add_column('games', sa.Column('status_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_games_status_id', 'games', 'game_statuses', ['status_id'], ['id'])


def downgrade():
    op.drop_constraint('fk_games_status_id', 'games', type_='foreignkey')
    op.drop_column('games', 'status_id')
    op.drop_table('game_statuses')
