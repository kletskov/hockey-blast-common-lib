"""Rename DivisionsGraphEdge to LevelsGraphEdge and update related fields

Revision ID: e81369b423bc
Revises: 1c368bfe6622
Create Date: 2025-01-29 17:56:49.782432

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e81369b423bc'
down_revision = '1c368bfe6622'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('levels_graph_edges',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('from_level_id', sa.Integer(), nullable=False),
    sa.Column('to_level_id', sa.Integer(), nullable=False),
    sa.Column('n_connections', sa.Integer(), nullable=False),
    sa.Column('ppg_ratio', sa.Float(), nullable=False),
    sa.ForeignKeyConstraint(['from_level_id'], ['levels.id'], ),
    sa.ForeignKeyConstraint(['to_level_id'], ['levels.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('from_level_id', 'to_level_id', name='_from_to_level_uc')
    )
    op.drop_table('divisions_graph_edges')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('divisions_graph_edges',
    sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
    sa.Column('from_division_id', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.Column('to_division_id', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.Column('n_connections', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.Column('ppg_ratio', sa.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=False),
    sa.ForeignKeyConstraint(['from_division_id'], ['divisions.id'], name='divisions_graph_edges_from_division_id_fkey'),
    sa.ForeignKeyConstraint(['to_division_id'], ['divisions.id'], name='divisions_graph_edges_to_division_id_fkey'),
    sa.PrimaryKeyConstraint('id', name='divisions_graph_edges_pkey'),
    sa.UniqueConstraint('from_division_id', 'to_division_id', name='_from_to_division_uc')
    )
    op.drop_table('levels_graph_edges')
    # ### end Alembic commands ###
