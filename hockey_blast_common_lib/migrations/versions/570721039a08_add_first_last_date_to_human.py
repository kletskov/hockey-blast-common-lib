"""add first/last date to Human

Revision ID: 570721039a08
Revises: 7b1f0058cd6d
Create Date: 2024-12-12 16:14:11.486061

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '570721039a08'
down_revision = '7b1f0058cd6d'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('humans', schema=None) as batch_op:
        batch_op.add_column(sa.Column('first_date', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('last_date', sa.Date(), nullable=True))
        batch_op.create_unique_constraint('_human_name_uc', ['first_name', 'middle_name', 'last_name'])

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('humans', schema=None) as batch_op:
        batch_op.drop_constraint('_human_name_uc', type_='unique')
        batch_op.drop_column('last_date')
        batch_op.drop_column('first_date')

    # ### end Alembic commands ###
