
from aio_pika.abc import AbstractIncomingMessage
from pydantic import ValidationError

from payment_service.messaging.contracts import PaymentRequestedEnvelope

async def handle_payment_requested(
    message: AbstractIncomingMessage,
) -> None:
    try:
        event = PaymentRequestedEnvelope.model_validate_json(message.body)

    except ValidationError as exc:
        print(
            "Permanent message validation error:",
            f"message_id={message.message_id}",
            f"errors={exc.error_count()}",
        )

        await message.reject(requeue=False)
        return
    
    await message.ack()

        