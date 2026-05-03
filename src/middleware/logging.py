"""Structured JSON logging middleware with per-request correlation ID."""
import json
import logging
import sys
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class StructuredLogger:
    """JSON stdout logger with request-scoped fields baked in at emission time."""

    def __init__(self):
        self._logger = logging.getLogger("agent-job")
        self._logger.setLevel(logging.INFO)
        # stdout handler if not already configured
        if not self._logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(logging.Formatter("%(message)s"))
            self._logger.addHandler(handler)

    def _make(self, level: str, event: str, **kw) -> str:
        return json.dumps({"level": level, "event": event, **kw}, ensure_ascii=False)

    def info(self, event: str, **kw):
        self._logger.info(self._make("INFO", event, **kw))

    def error(self, event: str, **kw):
        self._logger.error(self._make("ERROR", event, **kw))

    def warning(self, event: str, **kw):
        self._logger.warning(self._make("WARNING", event, **kw))

    def debug(self, event: str, **kw):
        self._logger.debug(self._make("DEBUG", event, **kw))


logger = StructuredLogger()


class LoggingMiddleware(BaseHTTPMiddleware):
    """Attaches X-Request-ID to every request and logs start/end in JSON."""

    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        logger.info(
            "request_started",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            client=request.client.host if request.client else None,
        )

        response = await call_next(request)

        logger.info(
            "request_finished",
            request_id=request_id,
            status_code=response.status_code,
        )
        response.headers["X-Request-ID"] = request_id

        return response
