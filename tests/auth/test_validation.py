from __future__ import annotations

import pytest

from agro_mirai.auth.validation import validate_name


def test_validate_name_requires_non_blank():
    validate_name("Ravi Kumar")
    with pytest.raises(ValueError):
        validate_name("")
    with pytest.raises(ValueError):
        validate_name("   ")
