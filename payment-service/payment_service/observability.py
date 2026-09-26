"""Small, dependency-free JSON logging for service boundaries."""

import json
import logging
import re
import time
import traceback
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request

SERVICE_NAME = "payment-service"
_FIELDS = (
    "request_id", "event_id", "order_id", "payment_id", "user_id", "message_id",
    "event_type", "status_code", "duration_ms", "method", "route",
    "retry_count", "topic", "partition", "offset", "outbox_id", "target_status",
)
_REQUEST_ID = re.compile(r"[A-Za-z0-9_-]{8,128}\Z")
_IDENTIFIER = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")
_IDENTIFIER_FIELDS = {
    "request_id", "event_id", "order_id", "payment_id", "user_id",
    "message_id", "outbox_id",
}
_context: ContextVar[dict[str, Any] | None] = ContextVar("log_context", default=None)


@contextmanager
def log_context(**fields: Any) -> Iterator[None]:
    """Bind safe identifiers for one request or broker message only."""
    token = _context.set({
        **(_context.get() or {}),
        **{k: v for k, v in fields.items() if k in _FIELDS},
    })
    try:
        yield
    finally:
        _context.reset(token)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "service": SERVICE_NAME,
            "logger": record.name,
            "event": (
                record.msg
                if isinstance(record.msg, str)
                and re.fullmatch(r"[a-z][a-z0-9_.]+", record.msg)
                else "legacy.log"
            ),
        }
        for key in _FIELDS:
            value = record.__dict__.get(key, (_context.get() or {}).get(key))
            if value is not None:
                if key in _IDENTIFIER_FIELDS:
                    value = str(value)
                    if not _IDENTIFIER.fullmatch(value):
                        continue
                data[key] = value
        if data["event"] == "legacy.log":
            # Legacy format arguments may contain credentials or payloads.
            data["message_template"] = record.msg if isinstance(record.msg, str) else record.name
        if record.exc_info:
            # Exception text can contain credentials or payloads; keep only the type.
            data["exception_type"] = record.exc_info[0].__name__
            data["stack"] = [
                f"{frame.filename}:{frame.lineno}:{frame.name}"
                for frame in traceback.extract_tb(record.exc_info[2])[-8:]
            ]
        return json.dumps(data, ensure_ascii=False, default=str)


def configure_logging() -> None:
    package_logger = logging.getLogger("payment_service")
    if any(isinstance(handler.formatter, JsonFormatter) for handler in package_logger.handlers):
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    package_logger.addHandler(handler)
    package_logger.setLevel(logging.INFO)
    package_logger.propagate = False


def install_http_logging(app: FastAPI) -> None:
    configure_logging()
    # The middleware emits one structured access event instead.
    logging.getLogger("uvicorn.access").disabled = True
    logger = logging.getLogger(f"{__name__}.http")

    @app.middleware("http")
    async def log_http_request(request: Request, call_next: Any) -> Any:
        candidate = request.headers.get("x-request-id", "")
        request_id = candidate if _REQUEST_ID.fullmatch(candidate) else str(uuid4())
        started = time.perf_counter()
        with log_context(request_id=request_id):
            try:
                response = await call_next(request)
            except Exception:
                logger.exception("http.request.failed")
                raise
            response.headers["X-Request-ID"] = request_id
            logger.log(
                logging.WARNING if response.status_code >= 500 else logging.INFO,
                "http.request.completed",
                extra={
                    "method": request.method,
                    "status_code": response.status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                    "route": getattr(request.scope.get("route"), "path", None),
                },
            )
            return response
