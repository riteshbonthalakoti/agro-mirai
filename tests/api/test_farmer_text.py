"""Module 39: plain-language rewrites of model-explanation text for farmers."""
from agro_mirai.api.farmer_text import in_karnataka, plain_advisory, plain_irrigation, plain_paragraph

BODY = (
    "The biggest factors behind this recommendation of muskmelon were: rainfall (0.00, increases the result); "
    "N (2020.00, increases the result). Caveat: muskmelon is not commonly grown in the Bellary/Karnataka region."
)


def test_advisory_is_plain_and_drops_wrong_region_caveat():
    out = plain_advisory(BODY, drop_regional_caveat=True)
    assert out.startswith("Best crop for your field: muskmelon.")
    assert "recent rainfall is 0 mm" in out
    assert "2020" not in out and "increases the result" not in out and "Bellary" not in out


def test_caveat_kept_inside_karnataka():
    assert "Bellary" in plain_advisory(BODY, drop_regional_caveat=False)


def test_irrigation_rationale_plain():
    text = ("Predicted irrigation need: medium (soil moisture 15.0%, season None). Water balance: "
            "ET0=3.71mm/day, crop ETc=4.45mm/day over 7 days minus 0.0mm rainfall received = 31.2mm net deficit -> 31.2mm recommended.")
    out = plain_irrigation(text)
    assert "31 mm of watering" in out and "ET0" not in out


def test_karnataka_box():
    assert in_karnataka(15.14, 76.92)
    assert not in_karnataka(17.68, 83.23)  # Visakhapatnam


def test_disease_paragraph_gets_an_actual_action_not_just_restated_readings():
    para = (
        "The biggest contributing factors behind this high disease risk were: "
        "temp_c_mean_14d (34.70, increases the result); humidity_pct_mean_14d (32.00, increases the result)."
    )
    out = plain_paragraph(para)
    assert "Chance of crop disease is high." in out
    assert "What to do:" in out
    assert "Scout field within 2 days" in out


def test_ph_factor_gets_a_plain_verdict_not_a_bare_number():
    para = "The biggest factors behind this recommendation of wheat were: Soil_pH (8.00, increases the result)."
    out = plain_paragraph(para)
    assert "soil acidity (pH) is 8" in out
    assert "slightly alkaline" in out


def test_irrigation_water_balance_inside_a_combined_advisory_body_is_also_simplified():
    # Previously only the standalone irrigation endpoint called
    # plain_irrigation() directly -- this paragraph, as it appears inside
    # Advisory.body (DecisionEngine.recommend's 3-paragraph join), used to
    # pass through plain_advisory() completely unrewritten.
    body = (
        "Muskmelon is a good fit for your field.\n\n"
        "Predicted irrigation need: medium (soil moisture 15.0%, season None). Water balance: "
        "ET0=3.71mm/day, crop ETc=4.45mm/day over 7 days minus 0.0mm rainfall received = 31.2mm net deficit -> 31.2mm recommended.\n\n"
        "The biggest contributing factors behind this low disease risk were: temp_c_mean_14d (25.00, increases the result)."
    )
    out = plain_advisory(body)
    assert "ET0" not in out and "net deficit" not in out
    assert "31 mm of watering" in out
