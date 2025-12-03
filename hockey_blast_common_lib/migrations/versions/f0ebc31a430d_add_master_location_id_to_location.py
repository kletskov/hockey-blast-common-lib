"""Add master_location_id to Location

Revision ID: f0ebc31a430d
Revises: 4c7b6623e76e
Create Date: 2025-11-26 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f0ebc31a430d'
down_revision = '4c7b6623e76e'
branch_labels = None
depends_on = None


def upgrade():
    # Add master_location_id column to locations table
    with op.batch_alter_table('locations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('master_location_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('locations_master_location_id_fkey', 'locations', ['master_location_id'], ['id'])


def downgrade():
    # Remove master_location_id column from locations table
    with op.batch_alter_table('locations', schema=None) as batch_op:
        batch_op.drop_constraint('locations_master_location_id_fkey', type_='foreignkey')
        batch_op.drop_column('master_location_id')
