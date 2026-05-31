"""Structured logging and request correlation.

Provides a JSON log formatter, a one-shot logging configurator, and an ASGI
middleware that assigns a correlation id to every request and binds it to the
log record (architecture §4.3). The correlation id is returned to callers via
the ``X-Correlation-ID`` response header so a client error can be traced to its
server-side log line.

Secrets never reach the logger: only the fields assembled here are emitted, and
configuration secrets are wrapped in ``SecretStr`` upstream (NFR-SC-1).

Author: Al Amin Ahamed.
"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

CORRELATION_ID_HEADER = "X-Correlation-ID"
"""Response header carrying the per-request correlation id."""

_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="-")
"""Process-local store for the active request's correlation id."""

# Standard ``LogRecord`` attributes; anything else on a record is treated as an
# explicit structured field and merged into the JSON payload.
_RESERVED_RECORD_KEYS = frozenset(
    logging.makeLogRecord({}).__dict__.keys() | {"message", "asctime", "taskName"}
)


def get_correlation_id() -> str:
    """Return the correlation id bound to the current context.

    Returns:
        str: The active correlation id, or ``"-"`` outside any request scope.
    """
    return _correlation_id.get()


def set_correlation_id(correlation_id: str) -> None:
    """Bind a correlation id to the current context.

    Args:
        correlation_id: The identifier to associate with subsequent log records.
    """
    _correlation_id.set(correlation_id)


class JsonFormatter(logging.Formatter):
    """Render log records as single-line JSON objects.

    The payload always includes the timestamp, level, logger name, message, and
    the active correlation id. Any non-reserved attributes attached to the record
    (for example via ``logger.info(msg, extra={...})``) are merged in, and an
    exception, if present, is formatted into an ``exc_info`` string.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Serialise a log record to a JSON string.

        Args:
            record: The log record to format.

        Returns:
            str: A compact JSON document describing the record.
        """
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": get_correlation_id(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED_RECORD_KEYS and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Install the JSON formatter on the root logger.

    Idempotent: replaces any existing handlers so repeated calls (for example
    in tests or worker bootstraps) do not duplicate output.

    Args:
        level: Root log level name (for example ``"INFO"`` or ``"DEBUG"``).
    """
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Assign and propagate a correlation id for every HTTP request.

    The id is taken from the inbound ``X-Correlation-ID`` header when present
    (so a value can be threaded across services) and otherwise generated. It is
    bound to the logging context for the duration of the request and echoed back
    on the response.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Bind a correlation id, process the request, and echo the id back.

        Args:
            request: The incoming request.
            call_next: The next handler in the middleware chain.

        Returns:
            Response: The downstream response with the correlation-id header set.
        """
        correlation_id = request.headers.get(CORRELATION_ID_HEADER) or uuid.uuid4().hex
        set_correlation_id(correlation_id)
        response = await call_next(request)
        response.headers[CORRELATION_ID_HEADER] = correlation_id
        return response
