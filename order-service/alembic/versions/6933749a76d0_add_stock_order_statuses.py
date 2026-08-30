"""add stock order statuses

Revision ID: 6933749a76d0
Revises: 26069e4c0b3d
Create Date: 2026-08-30 22:48:24.518587

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6933749a76d0"
down_revision: str | Sequence[str] | None = "26069e4c0b3d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.get_context().autocommit_block():
        op.execute(
            "ALTER TYPE order_status "
            "ADD VALUE IF NOT EXISTS 'pending_stock' "
            "BEFORE 'pending_payment'"
        )
        op.execute(
            "ALTER TYPE order_status "
            "ADD VALUE IF NOT EXISTS 'stock_failed' "
            "AFTER 'pending_stock'"
        )

    op.execute(
        "ALTER TABLE orders "
        "ALTER COLUMN status "
        "SET DEFAULT 'pending_stock'::order_status"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        "ALTER TABLE orders "
        "ALTER COLUMN status "
        "SET DEFAULT 'pending_payment'::order_status"
    )
    op.execute(
        "UPDATE orders "
        "SET status = 'pending_payment'::order_status "
        "WHERE status = 'pending_stock'::order_status"
    )
    op.execute(
        "UPDATE orders "
        "SET status = 'cancelled'::order_status "
        "WHERE status = 'stock_failed'::order_status"
    )
