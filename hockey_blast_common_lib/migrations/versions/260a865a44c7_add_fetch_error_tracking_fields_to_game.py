"""Add fetch error tracking fields to Game

Revision ID: 260a865a44c7
Revises: 3887ae51ff2e
Create Date: 2026-03-25 13:29:04.934241

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '260a865a44c7'
down_revision = '3887ae51ff2e'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('games', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_fetch_error', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('last_fetch_error_detail', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('last_fetch_error_time', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('games', schema=None) as batch_op:
        batch_op.drop_column('last_fetch_error_time')
        batch_op.drop_column('last_fetch_error_detail')
        batch_op.drop_column('last_fetch_error')
