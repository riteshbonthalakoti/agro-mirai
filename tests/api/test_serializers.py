"""drop_unset_source: an additive optional "source" field on
Advisory/CropRecommendation/DiseaseRiskAlert must come back as an absent
key (not JSON null) when unset, matching specs/core/enums.md's
documented convention for records predating the field."""
from agro_mirai.api.serializers import drop_unset_source


def test_drops_key_when_source_is_none():
    assert drop_unset_source({"id": "x", "source": None}) == {"id": "x"}


def test_keeps_key_when_source_is_set():
    assert drop_unset_source({"id": "x", "source": "llm"}) == {"id": "x", "source": "llm"}


def test_missing_source_key_is_a_no_op():
    assert drop_unset_source({"id": "x"}) == {"id": "x"}
