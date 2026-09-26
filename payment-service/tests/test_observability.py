import json
import logging

from payment_service.observability import JsonFormatter, log_context


def test_json_logging_keeps_identifiers_but_not_legacy_arguments() -> None:
    formatter = JsonFormatter()
    record = logging.LogRecord(
        "payment_service.test",
        logging.ERROR,
        __file__,
        1,
        "External error: %s",
        ("secret-token",),
        None,
    )
    with log_context(event_id="event-123", order_id="order-456"):
        output = json.loads(formatter.format(record))

    assert output["service"] == "payment-service"
    assert output["event_id"] == "event-123"
    assert output["order_id"] == "order-456"
    assert output["event"] == "legacy.log"
    assert "secret-token" not in json.dumps(output)
    assert "event_id" not in json.loads(formatter.format(record))


def test_untrusted_message_id_is_not_logged() -> None:
    record = logging.LogRecord(
        "payment_service.test", logging.INFO, __file__, 1, "message.processed", (), None
    )
    record.message_id = "buyer@example.com"

    output = json.loads(JsonFormatter().format(record))

    assert "message_id" not in output
    assert "buyer@example.com" not in json.dumps(output)
