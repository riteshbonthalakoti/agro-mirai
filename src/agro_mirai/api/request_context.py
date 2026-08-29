"""Per-request id: generated fresh server-side (never trusted from a
client-supplied header), stashed on ``flask.g``, echoed back as
``X-Request-Id``, and stamped onto every log record emitted while that
request is in flight — so one request's log lines are traceable end to
end without pulling in a new logging dependency.
"""
from __future__ import annotations

import logging
import uuid

from flask import Flask, g, request


class _RequestIdLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.request_id = getattr(g, "request_id", None)
        except RuntimeError:
            record.request_id = None
        return True


def init_request_logging(app: Flask) -> None:
    app.logger.addFilter(_RequestIdLogFilter())

    @app.before_request
    def _assign_request_id():
        g.request_id = str(uuid.uuid4())

    @app.after_request
    def _echo_request_id(response):
        response.headers["X-Request-Id"] = g.get("request_id", "")
        app.logger.info(
            "%s %s -> %s", request.method, request.path, response.status_code
        )
        return response
