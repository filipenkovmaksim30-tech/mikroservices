import argparse
import asyncio
import logging
from uuid import UUID

from aio_pika.abc import AbstractExchange, AbstractIncomingMessage, AbstractQueue
from pydantic import TypeAdapter, ValidationError

from messaging_lab.config import Settings
from messaging_lab.db.session import async_engine, async_session_factory
from messaging_lab.messaging.contracts.payments import PaymentResultEnvelope
from messaging_lab.messaging.rabbitmq.connection import connect_rabbitmq, create_channel
from messaging_lab.messaging.rabbitmq.publisher import publish_message
from messaging_lab.messaging.rabbitmq.topology.payment_result import (
    PAYMENT_EVENTS_EXCHANGE,
    PAYMENT_RESULTS_CONSUMER,
    PAYMENT_RESULTS_DLQ,
    PAYMENT_RESULTS_REDELIVERY_ROUTING_KEY,
)
from messaging_lab.observability import configure_logging
from messaging_lab.repositories.inbox import InboxRepository
from messaging_lab.repositories.orders import OrderRepository
from messaging_lab.services.payment_result_redrive import (
    PaymentResultRedriveService,
    RedriveStatus,
)

logger = logging.getLogger(__name__)

PAYMENT_RESULT_ADAPTER: TypeAdapter[PaymentResultEnvelope] = TypeAdapter(PaymentResultEnvelope)


async def get_one_dlq_message(
    queue: AbstractQueue,
) -> AbstractIncomingMessage | None:
    return await queue.get(no_ack=False, fail=False)


def parse_payment_result_message(
    message: AbstractIncomingMessage,
) -> PaymentResultEnvelope:
    return PAYMENT_RESULT_ADAPTER.validate_json(message.body)


async def redrive_message(
    message: AbstractIncomingMessage,
    event: PaymentResultEnvelope,
    exchange: AbstractExchange,
) -> None:
    await publish_message(
        exchange=exchange,
        routing_key=PAYMENT_RESULTS_REDELIVERY_ROUTING_KEY,
        body=message.body,
        message_id=str(event.event_id),
        correlation_id=str(event.correlation_id),
        headers={"x-retry-count": 0},
    )
    await message.ack()


async def run_payment_result_redrive(
    *,
    execute: bool,
    expected_event_id: UUID | None,
) -> None:
    connection = None
    message: AbstractIncomingMessage | None = None

    try:
        settings = Settings()
        connection = await connect_rabbitmq(settings.rabbitmq_url)
        channel = await create_channel(connection)

        exchange = await channel.get_exchange(
            PAYMENT_EVENTS_EXCHANGE,
            ensure=True,
        )
        dlq = await channel.get_queue(
            PAYMENT_RESULTS_DLQ,
            ensure=True,
        )

        message = await get_one_dlq_message(dlq)
        if message is None:
            logger.info("redrive.dlq_empty")
            return

        try:
            event = parse_payment_result_message(message)
        except ValidationError as exc:
            logger.error(
                "Invalid payment result in DLQ: message_id=%s errors=%s",
                message.message_id,
                exc.error_count(),
            )
            await message.nack(requeue=True)
            return
        except Exception:
            logger.exception(
                "Unexpected payment result parsing error: message_id=%s",
                message.message_id,
            )
            await message.nack(requeue=True)
            return

        if expected_event_id is not None and event.event_id != expected_event_id:
            logger.error(
                "DLQ head does not match requested event: expected_event_id=%s actual_event_id=%s",
                expected_event_id,
                event.event_id,
            )
            await message.nack(requeue=True)
            return

        async with async_session_factory() as session:
            service = PaymentResultRedriveService(
                order_repository=OrderRepository(session),
                inbox_repository=InboxRepository(session),
                consumer_name=PAYMENT_RESULTS_CONSUMER,
            )
            decision = await service.inspect(event)

        logger.info(
            "Payment result DLQ inspected: event_id=%s order_id=%s "
            "decision=%s reason=%s execute=%s",
            event.event_id,
            event.payload.order_id,
            decision.status.value,
            decision.reason,
            execute,
        )

        if not execute:
            logger.info(
                "Dry-run completed; returning message to DLQ: event_id=%s",
                event.event_id,
            )
            await message.nack(requeue=True)
            return

        if decision.status is not RedriveStatus.READY:
            logger.warning(
                "Redrive refused; returning message to DLQ: event_id=%s decision=%s",
                event.event_id,
                decision.status.value,
            )
            await message.nack(requeue=True)
            return

        await redrive_message(
            message=message,
            event=event,
            exchange=exchange,
        )
        logger.info(
            "Payment result redriven successfully: event_id=%s order_id=%s",
            event.event_id,
            event.payload.order_id,
        )
    except Exception:
        logger.exception("redrive.failed")
        if message is not None and not message.processed:
            try:
                await message.nack(requeue=True)
            except Exception:
                logger.exception("redrive.return_to_dlq_failed")
        raise
    finally:
        try:
            if connection is not None:
                await connection.close()
        finally:
            await async_engine.dispose()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect or redrive one message from the payment results DLQ",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Republish a READY message; without this flag the command is dry-run",
    )
    parser.add_argument(
        "--event-id",
        type=UUID,
        help="Expected event UUID; required with --execute",
    )
    arguments = parser.parse_args()
    if arguments.execute and arguments.event_id is None:
        parser.error("--event-id is required with --execute")
    return arguments


if __name__ == "__main__":
    configure_logging()
    arguments = parse_args()
    asyncio.run(
        run_payment_result_redrive(
            execute=arguments.execute,
            expected_event_id=arguments.event_id,
        )
    )
