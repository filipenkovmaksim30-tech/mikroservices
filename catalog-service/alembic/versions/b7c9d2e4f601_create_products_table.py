"""Create products table.

Revision ID: b7c9d2e4f601
Revises:
Create Date: 2026-08-18

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "b7c9d2e4f601"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create catalog products."""
    op.create_table(
        "products",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=200), nullable=True),
        sa.Column("price", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("stock_quantity", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "price >= 0",
            name="ck_products_price_non_negative",
        ),
        sa.CheckConstraint(
            "stock_quantity >= 0",
            name="ck_stock_quantity_non_negative",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_products_category", "products", ["category"], unique=False)


def downgrade() -> None:
    """Drop catalog products."""
    op.drop_index("ix_products_category", table_name="products")
    op.drop_table("products")
