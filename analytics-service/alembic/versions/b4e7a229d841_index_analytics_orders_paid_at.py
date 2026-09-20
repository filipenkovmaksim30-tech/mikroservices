"""Index analytics orders by payment time.

Revision ID: b4e7a229d841
Revises: ca05597ce07b
"""

from collections.abc import Sequence

from alembic import op

revision: str = "b4e7a229d841"
down_revision: str | Sequence[str] | None = "ca05597ce07b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_analytics_orders_paid_at", "analytics_orders", ["paid_at"])


def downgrade() -> None:
    op.drop_index("ix_analytics_orders_paid_at", table_name="analytics_orders")
