"""org to leagues

Revision ID: a383ee9d7d1f
Revises: 65f0e6a4787e
Create Date: 2024-12-10 22:54:43.113880

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a383ee9d7d1f'
down_revision = '65f0e6a4787e'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('leagues', schema=None) as batch_op:
        batch_op.add_column(sa.Column('org_id', sa.Integer(), nullable=True))
        batch_op.create_unique_constraint('_org_league_number_uc', ['org_id', 'league_number'])
        batch_op.create_foreign_key(None, 'organizations', ['org_id'], ['id'])

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('leagues', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_constraint('_org_league_number_uc', type_='unique')
        batch_op.drop_column('org_id')

    # ### end Alembic commands ###
