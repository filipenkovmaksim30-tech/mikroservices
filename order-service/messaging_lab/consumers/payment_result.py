
from aio_pika.abc import AbstractIncomingMessage
from pydantic import TypeAdapter, ValidationError
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from messaging_lab.messaging.contracts import PaymentResultEnvelope
from messaging_lab.repositories.inbox import InboxRepository
from messaging_lab.repositories.orders import OrderRepository
from messaging_lab.services.payment_result import PaymentResultService

PAYMENT_RESULT_ADAPTER = TypeAdapter(PaymentResultEnvelope)

async def handler_payment_result(
    message: AbstractIncomingMessage,
    consumer_name: str,
    session_factory: async_sessionmaker[AsyncSession]
) -> None:
    try:
        event = PAYMENT_RESULT_ADAPTER.validate_json(message.body)

    except ValidationError:
        await message.reject(requeue=False)
        return

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

    await message.ack()