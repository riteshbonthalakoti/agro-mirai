"""Flask API layer (Module 11) — exposes ``DecisionEngine`` and the
``DataStore`` behind HTTP endpoints matching ``specs/core/openapi.yaml``.

Nothing outside ``src/`` imports the model classes directly after this
module; everything goes through ``create_app``.
"""
from agro_mirai.api.app import create_app

__all__ = ["create_app"]
