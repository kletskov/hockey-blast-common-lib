"""Add skill_value and skill_propagation_sequence to Division model, add DivisionsGraphEdge model

Revision ID: 3ae7f7c42b44
Revises: e4a16ab84e2a
Create Date: 2025-01-28 17:19:56.434639

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3ae7f7c42b44'
down_revision = 'e4a16ab84e2a'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('divisions_graph_edges',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('from_division_id', sa.Integer(), nullable=False),
    sa.Column('to_division_id', sa.Integer(), nullable=False),
    sa.Column('n_connections', sa.Integer(), nullable=False),
    sa.Column('ppg_ratio', sa.Float(), nullable=False),
    sa.ForeignKeyConstraint(['from_division_id'], ['divisions.id'], ),
    sa.ForeignKeyConstraint(['to_division_id'], ['divisions.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('from_division_id', 'to_division_id', name='_from_to_division_uc')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('divisions_graph_edges')
    # ### end Alembic commands ###
