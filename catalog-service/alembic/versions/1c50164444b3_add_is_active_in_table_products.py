"""add is_active in table products

Revision ID: 1c50164444b3
Revises: b7c9d2e4f601
Create Date: 2026-08-29 14:10:55.637372

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa



revision: str = '1c50164444b3'
down_revision: str | Sequence[str] | None = 'b7c9d2e4f601'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "products",
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("products", "is_active")
