"""update order status for payments

Revision ID: 8c4f9a2d7b31
Revises: 27342bb357b5
Create Date: 2026-08-06

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "8c4f9a2d7b31"
down_revision: Union[str, Sequence[str], None] = "27342bb357b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE orders ALTER COLUMN status DROP DEFAULT")
    op.execute("ALTER TYPE order_status RENAME TO order_status_old")
    op.execute(
        "CREATE TYPE order_status AS ENUM "
        "('pending_payment', 'paid', 'payment_failed', 'cancelled')"
    )
    op.execute(
        """
        ALTER TABLE orders
        ALTER COLUMN status TYPE order_status
        USING (
            CASE status::text
                WHEN 'created' THEN 'pending_payment'
                WHEN 'canceled' THEN 'cancelled'
            END
        )::order_status
        """
    )
    op.execute(
        "ALTER TABLE orders ALTER COLUMN status "
        "SET DEFAULT 'pending_payment'::order_status"
    )
    op.execute("DROP TYPE order_status_old")


def downgrade() -> None:
    op.execute("ALTER TABLE orders ALTER COLUMN status DROP DEFAULT")
    op.execute("ALTER TYPE order_status RENAME TO order_status_new")
    op.execute("CREATE TYPE order_status AS ENUM ('created', 'canceled')")
    op.execute(
        """
        ALTER TABLE orders
        ALTER COLUMN status TYPE order_status
        USING (
            CASE status::text
                WHEN 'cancelled' THEN 'canceled'
                ELSE 'created'
            END
        )::order_status
        """
    )
    op.execute(
        "ALTER TABLE orders ALTER COLUMN status "
        "SET DEFAULT 'created'::order_status"
    )
    op.execute("DROP TYPE order_status_new")
