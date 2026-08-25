"""AGRO MIRAI application package.

Module 03 introduces the first application code: the data-acquisition
adapters under :mod:`agro_mirai.acquisition`. Everything here is built
against the contracts in ``specs/core`` (schema, enums, conventions) —
no module reaches an external HTTP/GEE client directly; it goes through
an adapter.
"""

__all__ = ["acquisition"]
