"""Make status_id NOT NULL

Revision ID: 2fd628dbd505
Revises: c277e526c6bb
Create Date: 2026-06-05 15:15:17.199455

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2fd628dbd505'
down_revision = 'c277e526c6bb'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('games', 'status_id',
           existing_type=sa.INTEGER(),
           nullable=False)


def downgrade():
    op.alter_column('games', 'status_id',
           existing_type=sa.INTEGER(),
           nullable=True)
