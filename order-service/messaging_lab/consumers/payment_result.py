import logging

from aio_pika.abc import AbstractExchange, AbstractIncomingMessage
from pydantic import TypeAdapter, ValidationError

from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from messaging_lab.messaging.contracts import PaymentResultEnvelope
from messaging_lab.messaging.rabbitmq.publisher import publish_message
from messaging_lab.messaging.rabbitmq.topology.payment_result import PAYMENT_RESULTS_RETRY_ROUTING_KEY
from messaging_lab.repositories.inbox import InboxRepository
from messaging_lab.repositories.orders import OrderRepository
from messaging_lab.services.payment_result import PaymentResultService
from messaging_lab.exceptions import PermanentPaymentResultError, OrderNotFoundError

logger = logging.getLogger(__name__)

PAYMENT_RESULT_ADAPTER = TypeAdapter(PaymentResultEnvelope)


MAX_RETRY_ATTEMPTS  = 3

async def retry_or_send_to_dlq(
    message: AbstractIncomingMessage,
    retry_exchange: AbstractExchange,
    retry_routing_key: str,
    event_id: str,
    correlation_id: str,
) -> None:
    raw_retry_count = (
        message.headers.get("x-retry-count", 0)
        if message.headers
        else 0
    )
    retry_count = int(raw_retry_count)

    if retry_count >= MAX_RETRY_ATTEMPTS:
        logger.error(
            "Retry attempts exhausted: message_id=%s retry_count=%s",
            message.message_id,
            retry_count,
        )
        await message.reject(requeue=False)
        return
    
    next_retry_count = retry_count + 1
            
    await publish_message(
        exchange=retry_exchange,
        routing_key=retry_routing_key,
        body=message.body,
        message_id=event_id,
        correlation_id=correlation_id,
        headers={
            "x-retry-count": next_retry_count
        },
    )
    await message.ack()

async def handler_payment_result(
    message: AbstractIncomingMessage,
    retry_exchange: AbstractExchange,
    consumer_name: str,
    session_factory: async_sessionmaker[AsyncSession]
) -> None:
    try:
        event = PAYMENT_RESULT_ADAPTER.validate_json(message.body)

    except ValidationError:
        await message.reject(requeue=False)
        return
    
    try:
        async with session_factory() as session:
            inbox_repository = InboxRepository(session)
            order_repository = OrderRepository(session)
            service = PaymentResultService(
                session=session,
                inbox_repository=inbox_repository,
                order_repository=order_repository,
                consumer_name=consumer_name,
            )

        
            await service.process(event=event)

    except PermanentPaymentResultError:
        await message.reject(requeue=False)
        return 

    except (OrderNotFoundError, SQLAlchemyError, OSError):
        await retry_or_send_to_dlq(
            message=message,
            retry_exchange=retry_exchange,
            retry_routing_key=PAYMENT_RESULTS_RETRY_ROUTING_KEY,
            event_id=str(event.event_id),
            correlation_id=str(event.correlation_id)
        )
        return

    await message.ack()