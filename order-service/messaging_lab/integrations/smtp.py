import aiosmtplib

from email.message import EmailMessage
from aiosmtplib import (
    SMTPAuthenticationError,
    SMTPException,
    SMTPRecipientRefused,
    SMTPRecipientsRefused,
    SMTPResponseException,
    SMTPSenderRefused,
    SMTPServerDisconnected,
    SMTPTimeoutError,
)

from messaging_lab.services.notifications import (
    PermanentNotificationError,
    TransientNotificationError,
)
from messaging_lab.messaging.contracts.notifications import (
    OrderNotificationEnvelopeV1,
    OrderPaidEnvelopeV1,
    OrderPaymentFailedEnvelopeV1,
)


class GmailSmtpNotificationProvider:
    def __init__(
        self,
        port: int,
        host: str,
        username: str,
        password: str,
        sender_email: str,
        start_tls: bool,
        use_tls: bool,
        timeout_seconds: float,
    ) -> None:
        if start_tls and use_tls:
            raise ValueError("start_tls and use_tls cannot both be enabled")
        self._port = port
        self._host = host
        self._username = username
        self._password = password
        self._sender_email = sender_email
        self._start_tls = start_tls
        self._use_tls = use_tls
        self._timeout_seconds = timeout_seconds

    def _build_order_paid_message(
        self,
        event: OrderPaidEnvelopeV1,
        idempotency_key: str,
    ) -> EmailMessage:
        message = EmailMessage()
        message["From"] = self._sender_email
        message["To"] = str(event.payload.receipt_email)
        message["Subject"] = f"Оплата заказа {event.payload.order_id} подтверждена"
        message["X-Idempotency-Key"] = idempotency_key
        message.set_content(
            "Здравствуйте!\n"
            f"Оплата заказа {event.payload.order_id} прошла успешно.\n"
            f"Сумма заказа: {event.payload.total_amount} {event.payload.currency}.\n"
            "Спасибо, что выбираете M-Shop."
        )
        return message

    def _build_order_payment_failed_message(
        self,
        event: OrderPaymentFailedEnvelopeV1,
        idempotency_key: str,
    ) -> EmailMessage:
        message = EmailMessage()
        message["From"] = self._sender_email
        message["To"] = str(event.payload.receipt_email)
        message["Subject"] = f"Оплата заказа {event.payload.order_id} не прошла"
        message["X-Idempotency-Key"] = idempotency_key
        message.set_content(
            "Здравствуйте!\n"
            f"Оплата заказа {event.payload.order_id} не прошла.\n"
            f"Сумма заказа: {event.payload.total_amount} {event.payload.currency}.\n"
            "Если нужна помощь, свяжитесь с поддержкой M-Shop."
        )
        return message

    async def send_order_notifications(
        self,
        event: OrderNotificationEnvelopeV1,
        idempotency_key: str,
    ) -> None:
        if isinstance(event, OrderPaidEnvelopeV1):
            message = self._build_order_paid_message(
                event=event,
                idempotency_key=idempotency_key,
            )
        else:
            message = self._build_order_payment_failed_message(
                event=event,
                idempotency_key=idempotency_key,
            )
        try:
            await aiosmtplib.send(
                message,
                hostname=self._host,
                port=self._port,
                username=self._username,
                password=self._password,
                start_tls=self._start_tls,
                use_tls=self._use_tls,
                timeout=self._timeout_seconds,
            )
        except SMTPAuthenticationError as exc:
            raise PermanentNotificationError("SMTP authentication failed") from exc
        except (
            SMTPSenderRefused,
            SMTPRecipientRefused,
            SMTPRecipientsRefused,
        ) as exc:
            raise PermanentNotificationError(
                "SMTP sender or recipient was refused",
            ) from exc
        except SMTPResponseException as exc:
            if 400 <= exc.code < 500:
                raise TransientNotificationError(
                    f"Temporary SMTP response {exc.code}",
                ) from exc
            raise PermanentNotificationError(
                f"Permanent SMTP response {exc.code}",
            ) from exc
        except (
            SMTPServerDisconnected,
            SMTPTimeoutError,
            OSError,
        ) as exc:
            raise TransientNotificationError("SMTP connection failed") from exc
        except SMTPException as exc:
            raise TransientNotificationError("Unexpected SMTP error") from exc
