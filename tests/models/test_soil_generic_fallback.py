from agro_mirai.models.soil_type_typical_values import lookup_typical_moisture_pct, lookup_typical_values


def test_unknown_or_missing_soil_gets_generic_profile():
    for st in ("unknown", None, ""):
        vals = lookup_typical_values(st)
        assert vals is not None and 5 < vals["ph"] < 9
        assert lookup_typical_moisture_pct(st) is not None


def test_real_soil_type_unchanged():
    assert lookup_typical_values("Black")["ph"] == 8.0
    assert lookup_typical_moisture_pct("red") == 15.0
