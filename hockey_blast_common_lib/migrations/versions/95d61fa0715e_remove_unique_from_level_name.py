"""Remove unique from level name

Revision ID: 95d61fa0715e
Revises: f57f022df273
Create Date: 2025-03-30 18:03:03.234329

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '95d61fa0715e'
down_revision = 'f57f022df273'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('levels', schema=None) as batch_op:
        batch_op.drop_constraint('levels_level_name_key', type_='unique')

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('levels', schema=None) as batch_op:
        batch_op.create_unique_constraint('levels_level_name_key', ['level_name'])

    # ### end Alembic commands ###
