"""0003_boundary_tables_and_versioning

Revision ID: 0003_boundary_tables_and_versioning
Revises: 0002_add_reviewer_verify_ai_tables
Create Date: 2026-11-10 04:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0003_boundary_tables_and_versioning'
down_revision: Union[str, None] = '0002_add_reviewer_verify_ai_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add boundary and regional columns to farms table
    op.add_column('farms', sa.Column('boundary_version', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('farms', sa.Column('crs', sa.String(), nullable=False, server_default='EPSG:4326'))
    op.add_column('farms', sa.Column('area_sq_meters', sa.Float(), nullable=False, server_default='0.0'))
    op.add_column('farms', sa.Column('area_acres', sa.Float(), nullable=False, server_default='0.0'))
    op.add_column('farms', sa.Column('is_valid', sa.Boolean(), nullable=False, server_default=sa.text('true')))
    op.add_column('farms', sa.Column('validation_details', sa.Text(), nullable=True))
    op.add_column('farms', sa.Column('season', sa.String(), nullable=True))
    op.add_column('farms', sa.Column('district', sa.String(), nullable=True))
    op.add_column('farms', sa.Column('state', sa.String(), nullable=True))
    op.add_column('farms', sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True))

    # 2. Create boundary_vertices table
    op.create_table(
        'boundary_vertices',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('farm_id', sa.String(), nullable=False),
        sa.Column('boundary_version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('horizontal_accuracy', sa.Float(), nullable=True),
        sa.Column('observation_timestamp', sa.DateTime(), nullable=True),
        sa.Column('collection_method', sa.String(), nullable=True, server_default='WALK_AND_MARK'),
        sa.Column('vertex_sequence', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['farm_id'], ['farms.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_boundary_vertices_farm_id', 'boundary_vertices', ['farm_id'])
    op.create_index('ix_boundary_vertices_version', 'boundary_vertices', ['farm_id', 'boundary_version'])

    # 3. Create boundary_history table
    op.create_table(
        'boundary_history',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('farm_id', sa.String(), nullable=False),
        sa.Column('boundary_version', sa.Integer(), nullable=False),
        sa.Column('boundary_geojson', sa.Text(), nullable=False),
        sa.Column('area_sq_meters', sa.Float(), nullable=False),
        sa.Column('area_acres', sa.Float(), nullable=False),
        sa.Column('crs', sa.String(), nullable=False, server_default='EPSG:4326'),
        sa.Column('validation_details', sa.Text(), nullable=True),
        sa.Column('superseded_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['farm_id'], ['farms.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_boundary_history_farm_id', 'boundary_history', ['farm_id'])
    op.create_index('ix_boundary_history_version', 'boundary_history', ['farm_id', 'boundary_version'])


def downgrade() -> None:
    op.drop_table('boundary_history')
    op.drop_table('boundary_vertices')
    op.drop_column('farms', 'updated_at')
    op.drop_column('farms', 'state')
    op.drop_column('farms', 'district')
    op.drop_column('farms', 'season')
    op.drop_column('farms', 'validation_details')
    op.drop_column('farms', 'is_valid')
    op.drop_column('farms', 'area_acres')
    op.drop_column('farms', 'area_sq_meters')
    op.drop_column('farms', 'crs')
    op.drop_column('farms', 'boundary_version')
