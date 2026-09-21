"""add payment processing claim fields

Revision ID: 391449d0db3a
Revises: 2174cadb2270
Create Date: 2026-09-21 20:30:18.320887

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = '391449d0db3a'
down_revision: str | Sequence[str] | None = '2174cadb2270'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.get_context().autocommit_block():
        op.execute(
            "ALTER TYPE payment_status "
            "ADD VALUE IF NOT EXISTS 'processing' AFTER 'pending'"
        )

    op.add_column(
        'payments',
        sa.Column('processing_token', sa.Uuid(), nullable=True),
    )
    op.add_column(
        'payments',
        sa.Column(
            'processing_expires_at',
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        'payments',
        sa.Column(
            'processing_attempts',
            sa.Integer(),
            server_default='0',
            nullable=False,
        ),
    )

    op.drop_constraint(
        'ck_payments_status_fields_consistent',
        'payments',
        type_='check',
    )
    op.create_check_constraint(
        'ck_payments_status_fields_consistent',
        'payments',
        "(status = 'pending' "
        "AND completed_at IS NULL "
        "AND failure_code IS NULL "
        "AND processing_token IS NULL "
        "AND processing_expires_at IS NULL) "
        "OR (status = 'processing' "
        "AND completed_at IS NULL "
        "AND failure_code IS NULL "
        "AND processing_token IS NOT NULL "
        "AND processing_expires_at IS NOT NULL) "
        "OR (status = 'succeeded' "
        "AND completed_at IS NOT NULL "
        "AND failure_code IS NULL "
        "AND processing_token IS NULL "
        "AND processing_expires_at IS NULL) "
        "OR (status = 'failed' "
        "AND completed_at IS NOT NULL "
        "AND failure_code IS NOT NULL "
        "AND processing_token IS NULL "
        "AND processing_expires_at IS NULL)",
    )
    op.create_check_constraint(
        'ck_payments_processing_attempts_non_negative',
        'payments',
        'processing_attempts >= 0',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM payments
                WHERE status = 'processing'
            ) THEN
                RAISE EXCEPTION
                    'Cannot downgrade while payments are in processing status';
            END IF;
        END
        $$;
        """
    )

    op.drop_constraint(
        'ck_payments_status_fields_consistent',
        'payments',
        type_='check',
    )
    op.drop_constraint('ck_payments_processing_attempts_non_negative', 'payments', type_='check')
    op.drop_column('payments', 'processing_attempts')
    op.drop_column('payments', 'processing_expires_at')
    op.drop_column('payments', 'processing_token')

    op.execute("ALTER TABLE payments ALTER COLUMN status DROP DEFAULT")
    op.execute("ALTER TYPE payment_status RENAME TO payment_status_with_processing")
    op.execute("CREATE TYPE payment_status AS ENUM ('pending', 'succeeded', 'failed')")
    op.execute(
        "ALTER TABLE payments "
        "ALTER COLUMN status TYPE payment_status "
        "USING status::text::payment_status"
    )
    op.execute(
        "ALTER TABLE payments "
        "ALTER COLUMN status SET DEFAULT 'pending'::payment_status"
    )
    op.execute("DROP TYPE payment_status_with_processing")

    op.create_check_constraint(
        'ck_payments_status_fields_consistent',
        'payments',
        "(status = 'pending' AND completed_at IS NULL AND failure_code IS NULL) "
        "OR (status = 'succeeded' AND completed_at IS NOT NULL AND failure_code IS NULL) "
        "OR (status = 'failed' AND completed_at IS NOT NULL AND failure_code IS NOT NULL)",
    )
