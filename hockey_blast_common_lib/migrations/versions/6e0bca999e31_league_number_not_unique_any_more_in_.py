"""league_number not unique any more in dependents

Revision ID: 6e0bca999e31
Revises: 392cea1da5ca
Create Date: 2024-12-10 22:52:11.140592

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6e0bca999e31'
down_revision = '392cea1da5ca'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('levels_monthly', schema=None) as batch_op:
        batch_op.drop_constraint('levels_monthly_league_number_fkey', type_='foreignkey')

    with op.batch_alter_table('seasons', schema=None) as batch_op:
        batch_op.drop_constraint('seasons_league_number_fkey', type_='foreignkey')

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('seasons', schema=None) as batch_op:
        batch_op.create_foreign_key('seasons_league_number_fkey', 'leagues', ['league_number'], ['league_number'])

    with op.batch_alter_table('levels_monthly', schema=None) as batch_op:
        batch_op.create_foreign_key('levels_monthly_league_number_fkey', 'leagues', ['league_number'], ['league_number'])

    # ### end Alembic commands ###
