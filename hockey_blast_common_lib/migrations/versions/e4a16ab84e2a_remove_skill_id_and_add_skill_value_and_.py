"""Remove skill_id and add skill_value and skill_sequence_number fields to Division model

Revision ID: e4a16ab84e2a
Revises: 64807af5172b
Create Date: 2025-01-27 16:26:23.588036

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e4a16ab84e2a'
down_revision = '64807af5172b'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('divisions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('skill_value', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('skill_propagation_sequence', sa.Integer(), nullable=True))
        batch_op.drop_constraint('divisions_skill_id_fkey', type_='foreignkey')
        batch_op.drop_column('skill_id')

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('divisions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('skill_id', sa.INTEGER(), autoincrement=False, nullable=True))
        batch_op.create_foreign_key('divisions_skill_id_fkey', 'skills', ['skill_id'], ['id'])
        batch_op.drop_column('skill_propagation_sequence')
        batch_op.drop_column('skill_value')

    # ### end Alembic commands ###
