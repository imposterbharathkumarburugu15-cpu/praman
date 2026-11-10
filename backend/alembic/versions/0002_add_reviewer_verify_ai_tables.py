"""0002_add_reviewer_verify_ai_tables

Revision ID: 0002_add_reviewer_verify_ai_tables
Revises: 0001_initial_schema
Create Date: 2026-11-09 22:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0002_add_reviewer_verify_ai_tables'
down_revision: Union[str, None] = '0001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 0. Ensure alembic_version column is wide enough for descriptive revision names
    bind = op.get_bind()
    if bind and bind.dialect.name == 'postgresql':
        op.execute("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(64);")

    # 1. AI Assessments table
    op.create_table(
        'ai_assessments',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('evidence_id', sa.String(), nullable=False),
        sa.Column('blur_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('is_blurry', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('exposure_under_pct', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('exposure_over_pct', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('is_exposure_valid', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('width', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('height', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_resolution_valid', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('sha256', sa.String(length=64), nullable=False),
        sa.Column('phash', sa.String(length=64), nullable=False),
        sa.Column('nearest_phash_distance', sa.Integer(), nullable=True),
        sa.Column('is_duplicate', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('predicted_crop_class', sa.String(), nullable=True),
        sa.Column('crop_confidence', sa.Float(), nullable=True),
        sa.Column('is_crop_consistent', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('ela_variance', sa.Float(), nullable=True),
        sa.Column('noise_variance', sa.Float(), nullable=True),
        sa.Column('is_tamper_suspected', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('recommendation', sa.String(), nullable=False, server_default='AUTO_APPROVE'),
        sa.Column('assessment_json', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['evidence_id'], ['evidence.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_ai_assessments_evidence_id'), 'ai_assessments', ['evidence_id'], unique=False)

    # 2. Review Decisions table
    op.create_table(
        'review_decisions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('evidence_id', sa.String(), nullable=False),
        sa.Column('reviewer_id', sa.String(), nullable=False),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('new_state', sa.String(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('decided_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['evidence_id'], ['evidence.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint("action IN ('APPROVE', 'REJECT', 'REQUEST_RETAKE')", name='ck_review_action'),
    )
    op.create_index(op.f('ix_review_decisions_evidence_id'), 'review_decisions', ['evidence_id'], unique=False)
    op.create_index(op.f('ix_review_decisions_reviewer_id'), 'review_decisions', ['reviewer_id'], unique=False)

    # 3. Merkle Batches table
    op.create_table(
        'merkle_batches',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('merkle_root', sa.String(length=64), nullable=False),
        sa.Column('leaf_count', sa.Integer(), nullable=False),
        sa.Column('evidence_ids_json', sa.Text(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='COMMITTED_TO_LEDGER'),
        sa.Column('checkpoint_id', sa.String(), nullable=True),
        sa.Column('checkpoint_signature', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_merkle_batches_merkle_root'), 'merkle_batches', ['merkle_root'], unique=False)

    # 4. Public Tokens table
    op.create_table(
        'public_tokens',
        sa.Column('token', sa.String(length=128), nullable=False),
        sa.Column('evidence_id', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='ACTIVE'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['evidence_id'], ['evidence.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('token'),
    )
    op.create_index(op.f('ix_public_tokens_token'), 'public_tokens', ['token'], unique=True)
    op.create_index(op.f('ix_public_tokens_evidence_id'), 'public_tokens', ['evidence_id'], unique=False)


def downgrade() -> None:
    op.drop_table('public_tokens')
    op.drop_table('merkle_batches')
    op.drop_table('review_decisions')
    op.drop_table('ai_assessments')
