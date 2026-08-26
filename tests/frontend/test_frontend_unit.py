"""Module 14 — unit tests for frontend response-shape handling
(``_safe_get`` / ``_safe_get_list`` degrade gracefully instead of
raising) using a mocked API layer. Form-validation logic itself is
exercised end to end in test_frontend_integration.py's
``test_feedback_form_rejects_invalid_rating`` since it lives inline in
the route handler, not as a standalone function.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from agro_mirai.api.frontend_client import ApiError
from agro_mirai.api.routes import frontend


def _api_error(status_code, message="boom"):
    return ApiError(status_code, {"error": {"code": "X", "message": message}})


class TestSafeGet:
    def test_returns_payload_on_success(self):
        with patch.object(frontend, "api_get", return_value={"ok": True}):
            assert frontend._safe_get("/x") == {"ok": True}

    def test_returns_none_on_404(self):
        with patch.object(frontend, "api_get", side_effect=_api_error(404)):
            assert frontend._safe_get("/x") is None

    def test_returns_none_on_422(self):
        with patch.object(frontend, "api_get", side_effect=_api_error(422)):
            assert frontend._safe_get("/x") is None

    def test_reraises_on_500(self):
        with patch.object(frontend, "api_get", side_effect=_api_error(500)):
            with pytest.raises(ApiError):
                frontend._safe_get("/x")


class TestSafeGetList:
    def test_returns_items_on_success(self):
        with patch.object(frontend, "api_get", return_value={"items": [1, 2]}):
            assert frontend._safe_get_list("/x") == [1, 2]

    def test_returns_empty_list_on_404(self):
        with patch.object(frontend, "api_get", side_effect=_api_error(404)):
            assert frontend._safe_get_list("/x") == []

    def test_returns_empty_list_on_422(self):
        with patch.object(frontend, "api_get", side_effect=_api_error(422)):
            assert frontend._safe_get_list("/x") == []

    def test_reraises_on_500(self):
        with patch.object(frontend, "api_get", side_effect=_api_error(500)):
            with pytest.raises(ApiError):
                frontend._safe_get_list("/x")


class TestApiError:
    def test_extracts_message_from_payload(self):
        err = _api_error(400, "bad input")
        assert "bad input" in str(err)

    def test_falls_back_when_payload_missing_message(self):
        err = ApiError(500, {})
        assert "API error" in str(err)
