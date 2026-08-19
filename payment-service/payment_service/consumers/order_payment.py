
from aio_pika.abc import AbstractIncomingMessage
from pydantic import ValidationError

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from payment_service.repositories.inbox import InboxRepository
from payment_service.repositories.payments import PaymentRepository
from payment_service.messaging.contracts import PaymentRequestedEnvelope
from payment_service.services.payment_processing import PaymentProcessingService
from payment_service.exceptions import PaymentRequestConflictError

async def handle_payment_requested(
    message: AbstractIncomingMessage,
    consumer_name: str,
    session_factory: async_sessionmaker[AsyncSession]
) -> None:
    try:
        event = PaymentRequestedEnvelope.model_validate_json(message.body)
        async with session_factory() as session:
            inbox_repository = InboxRepository(session)
            payment_repository = PaymentRepository(session)
            service = PaymentProcessingService(
                session=session, 
                inbox_repository=inbox_repository,
                payment_repository=payment_repository, 
                consumer_name=consumer_name)
            await service.process(event)
        
    except ValidationError as exc:
        print(
            "Permanent message validation error:",
            f"message_id={message.message_id}",
            f"errors={exc.error_count()}",
        )
        await message.reject(requeue=False)
        return
    
    except PaymentRequestConflictError:
        await message.reject(requeue=False)
        return
    
    await message.ack()

        