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
