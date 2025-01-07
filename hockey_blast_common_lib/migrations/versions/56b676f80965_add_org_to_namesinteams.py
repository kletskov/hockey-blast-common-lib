"""add org to NamesInTeams

Revision ID: 56b676f80965
Revises: 9bfd97dfccf4
Create Date: 2024-12-11 12:24:17.788207

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '56b676f80965'
down_revision = '9bfd97dfccf4'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('names_in_teams', schema=None) as batch_op:
        batch_op.add_column(sa.Column('org_id', sa.Integer(), nullable=True))
        batch_op.drop_constraint('_team_name_uc', type_='unique')
        batch_op.create_unique_constraint('_org_team_name_uc', ['org_id', 'team_id', 'first_name', 'middle_name', 'last_name'])
        batch_op.create_foreign_key(None, 'organizations', ['org_id'], ['id'])

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('names_in_teams', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_constraint('_org_team_name_uc', type_='unique')
        batch_op.create_unique_constraint('_team_name_uc', ['team_id', 'first_name', 'middle_name', 'last_name'])
        batch_op.drop_column('org_id')

    # ### end Alembic commands ###