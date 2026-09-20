"""JSON error envelope for the API layer.

Every 400/401/404/422/500 response uses the ``ErrorEnvelope`` shape from
``specs/core/openapi.yaml``: ``{"error": {"code", "message", "details"}}``.
Flask's default HTML error pages are never returned.
"""
from __future__ import annotations

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, details: dict | None = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details or {}


def _envelope(code: str, message: str, details: dict | None = None) -> dict:
    return {"error": {"code": code, "message": message, "details": details or {}}}


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ApiError)
    def _handle_api_error(err: ApiError):
        return jsonify(_envelope(err.code, err.message, err.details)), err.status

    @app.errorhandler(HTTPException)
    def _handle_http_exception(err: HTTPException):
        return jsonify(_envelope(err.name.upper().replace(" ", "_"), err.description or err.name)), err.code

    @app.errorhandler(Exception)
    def _handle_unexpected(err: Exception):
        app.logger.exception("Unhandled error")
        return jsonify(_envelope("INTERNAL_ERROR", "An unexpected error occurred")), 500
