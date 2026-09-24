from agro_mirai.models.ecocrop import score_crops, table


def test_table_has_all_22_crops():
    assert len(table()) == 22


def test_scores_are_between_0_and_1_and_sorted():
    fits = score_crops(26.0, 7.0, "red", 100.0)
    scores = [f.score for f in fits]
    assert all(0.0 <= s <= 1.0 for s in scores)
    assert scores == sorted(scores, reverse=True)


def test_cool_temperature_prefers_cool_crops():
    top = [f.crop for f in score_crops(17.0, 6.0, "mountain", 250.0)[:4]]
    assert {"coffee", "apple", "kidneybeans"} & set(top)


def test_missing_ph_and_rain_still_scores():
    assert score_crops(28.0, None, None, None)[0].score > 0


def test_season_moves_the_pick():
    from agro_mirai.models.ecocrop import season_factor

    assert season_factor("cotton", 7) == 1.0
    assert season_factor("cotton", 9) == 0.85
    assert season_factor("cotton", 2) == 0.6
    assert season_factor("mango", 2) == 0.9  # perennial: no calendar, small commitment penalty
    kharif = {"cotton", "maize", "pigeonpeas", "mothbeans", "mungbean", "blackgram", "rice"}
    rabi = {"chickpea", "lentil", "maize", "rice", "kidneybeans"}
    july = [f.crop for f in score_crops(26.5, 7.5, "black", 100.0, None, 7, 600.0)[:2]]
    nov = [f.crop for f in score_crops(26.5, 7.5, "black", 100.0, None, 11, 600.0)[:2]]
    assert set(july) <= kharif and set(nov) <= rabi and "chickpea" in nov


def test_real_annual_rain_separates_wet_and_dry_climates():
    wet = score_crops(23.0, 6.0, "laterite", None, None, 7, 1900.0)[0].crop
    dry = score_crops(26.0, 7.5, "black", None, None, 7, 400.0)
    assert wet in {"coffee", "coconut", "rice", "orange", "papaya", "banana"}
    top_dry = [f.crop for f in dry[:6]]
    assert "coffee" not in top_dry and "coconut" not in top_dry
