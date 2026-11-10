"""0001_initial_schema

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-11-09 21:42:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Farmers table
    op.create_table(
        'farmers',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('full_name', sa.String(), nullable=False),
        sa.Column('phone_number', sa.String(), nullable=False),
        sa.Column('language_pref', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('phone_number'),
        sa.CheckConstraint("language_pref IN ('te', 'hi', 'en')", name='ck_farmer_language'),
    )
    op.create_index(op.f('ix_farmers_phone_number'), 'farmers', ['phone_number'], unique=True)

    # 2. Devices table
    op.create_table(
        'devices',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('farmer_id', sa.String(), nullable=False),
        sa.Column('public_key_pem', sa.Text(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='ACTIVE'),
        sa.Column('last_sequence_number', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['farmer_id'], ['farmers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint("status IN ('ACTIVE', 'REVOKED', 'SUSPENDED')", name='ck_device_status'),
    )
    op.create_index(op.f('ix_devices_farmer_id'), 'devices', ['farmer_id'], unique=False)

    # 3. Farms table
    op.create_table(
        'farms',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('farmer_id', sa.String(), nullable=False),
        sa.Column('farm_name', sa.String(), nullable=False),
        sa.Column('crop_type', sa.String(), nullable=False),
        sa.Column('boundary_geojson', sa.Text(), nullable=False),
        sa.Column('area_hectares', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['farmer_id'], ['farmers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_farms_farmer_id'), 'farms', ['farmer_id'], unique=False)

    # 4. Evidence table
    op.create_table(
        'evidence',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('farm_id', sa.String(), nullable=False),
        sa.Column('device_id', sa.String(), nullable=False),
        sa.Column('sequence_number', sa.Integer(), nullable=False),
        sa.Column('lifecycle_stage', sa.String(), nullable=False),
        sa.Column('image_hash', sa.String(), nullable=False),
        sa.Column('canonical_envelope_json', sa.Text(), nullable=False),
        sa.Column('signature_b64', sa.Text(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='DURABLY_ACKED'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['farm_id'], ['farms.id']),
        sa.ForeignKeyConstraint(['device_id'], ['devices.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('device_id', 'sequence_number', name='uq_device_sequence'),
    )
    op.create_index(op.f('ix_evidence_farm_id'), 'evidence', ['farm_id'], unique=False)
    op.create_index(op.f('ix_evidence_device_id'), 'evidence', ['device_id'], unique=False)
    op.create_index(op.f('ix_evidence_image_hash'), 'evidence', ['image_hash'], unique=False)

    # 5. Audit log table
    op.create_table(
        'audit_log',
        sa.Column('log_id', sa.String(), nullable=False),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('entity_type', sa.String(), nullable=False),
        sa.Column('entity_id', sa.String(), nullable=False),
        sa.Column('actor_id', sa.String(), nullable=False),
        sa.Column('previous_state', sa.String(), nullable=True),
        sa.Column('new_state', sa.String(), nullable=False),
        sa.Column('payload_hash', sa.String(), nullable=False),
        sa.Column('prev_log_hash', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('log_id'),
    )
    op.create_index(op.f('ix_audit_log_event_type'), 'audit_log', ['event_type'], unique=False)
    op.create_index(op.f('ix_audit_log_entity_type'), 'audit_log', ['entity_type'], unique=False)
    op.create_index(op.f('ix_audit_log_entity_id'), 'audit_log', ['entity_id'], unique=False)

    # 6. Audit immutability triggers (for postgresql)
    bind = op.get_bind()
    if bind and bind.dialect.name == 'postgresql':
        op.execute("""
            CREATE OR REPLACE FUNCTION audit_log_prohibit_update()
            RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'Audit log records are immutable and cannot be updated';
            END;
            $$ LANGUAGE plpgsql;

            CREATE OR REPLACE FUNCTION audit_log_prohibit_delete()
            RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'Audit log records are append-only and cannot be deleted';
            END;
            $$ LANGUAGE plpgsql;

            DROP TRIGGER IF EXISTS prohibit_audit_update ON audit_log;
            CREATE TRIGGER prohibit_audit_update
            BEFORE UPDATE ON audit_log
            FOR EACH ROW EXECUTE FUNCTION audit_log_prohibit_update();

            DROP TRIGGER IF EXISTS prohibit_audit_delete ON audit_log;
            CREATE TRIGGER prohibit_audit_delete
            BEFORE DELETE ON audit_log
            FOR EACH ROW EXECUTE FUNCTION audit_log_prohibit_delete();
        """)


def downgrade() -> None:
    bind = op.get_bind()
    if bind and bind.dialect.name == 'postgresql':
        op.execute("DROP TRIGGER IF EXISTS prohibit_audit_delete ON audit_log;")
        op.execute("DROP TRIGGER IF EXISTS prohibit_audit_update ON audit_log;")
        op.execute("DROP FUNCTION IF EXISTS audit_log_prohibit_delete();")
        op.execute("DROP FUNCTION IF EXISTS audit_log_prohibit_update();")

    op.drop_table('audit_log')
    op.drop_table('evidence')
    op.drop_table('farms')
    op.drop_table('devices')
    op.drop_table('farmers')
