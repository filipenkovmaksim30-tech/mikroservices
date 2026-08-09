"""split kafka and rabbitmq outbox

Revision ID: 27342bb357b5
Revises: 51d1cf100d72
Create Date: 2026-08-02 14:08:49.845791

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '27342bb357b5'
down_revision: Union[str, Sequence[str], None] = '51d1cf100d72'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.rename_table(
        "outbox_events",
        "rabbitmq_outbox_events",
    )
    op.execute(
        "ALTER TABLE rabbitmq_outbox_events "
        "RENAME CONSTRAINT ck_outbox_events_event_version_positive "
        "TO ck_rabbitmq_outbox_events_event_version_positive"
    )
    op.execute(
        "ALTER TABLE rabbitmq_outbox_events "
        "RENAME CONSTRAINT outbox_events_pkey "
        "TO rabbitmq_outbox_events_pkey"
    )
    op.execute(
        "ALTER INDEX ix_outbox_events_unpublished_occurred_at "
        "RENAME TO ix_rabbitmq_outbox_events_unpublished_occurred_at"
    )

    op.create_table('kafka_outbox_events',
    sa.Column('event_id', sa.Uuid(), nullable=False),
    sa.Column('aggregate_id', sa.Uuid(), nullable=False),
    sa.Column('event_type', sa.String(length=100), nullable=False),
    sa.Column('event_version', sa.SmallInteger(), server_default='1', nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('occurred_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint('event_version > 0', name='ck_kafka_outbox_events_event_version_positive'),
    sa.PrimaryKeyConstraint('event_id')
    )
    op.create_index('ix_kafka_outbox_events_unpublished_occurred_at', 'kafka_outbox_events', ['occurred_at'], unique=False, postgresql_where=sa.text('published_at IS NULL'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_kafka_outbox_events_unpublished_occurred_at', table_name='kafka_outbox_events', postgresql_where=sa.text('published_at IS NULL'))
    op.drop_table('kafka_outbox_events')

    op.execute(
        "ALTER INDEX ix_rabbitmq_outbox_events_unpublished_occurred_at "
        "RENAME TO ix_outbox_events_unpublished_occurred_at"
    )
    op.execute(
        "ALTER TABLE rabbitmq_outbox_events "
        "RENAME CONSTRAINT rabbitmq_outbox_events_pkey "
        "TO outbox_events_pkey"
    )
    op.execute(
        "ALTER TABLE rabbitmq_outbox_events "
        "RENAME CONSTRAINT ck_rabbitmq_outbox_events_event_version_positive "
        "TO ck_outbox_events_event_version_positive"
    )
    op.rename_table(
        "rabbitmq_outbox_events",
        "outbox_events",
    )
