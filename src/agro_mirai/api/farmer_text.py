"""Plain-language rewrites of the model-explanation text, for farmers.

The stored explanation strings are model-facing ("Temperature_C (26.40,
increases the result); N (2020.00, ...)"), and the crop caveat always talks
about "Bellary/Karnataka" whatever the field's location. The mobile app used
to show that raw text. These helpers turn it into short sentences a farmer can
read (and that the translation/voice services can handle). Nothing stored
changes: responses gain additive ``*_plain`` fields next to the originals.

Soil N/P/K numbers are never echoed: their units come from SoilGrids /
soil-type fallbacks and are not comparable to what a farmer knows (kg/acre),
so only the nutrient's name is mentioned.
"""
import re

from agro_mirai.models.disease_risk_scoring import RISK_ACTION

# feature key -> (plain label, unit, show number?)
_FEATURES: dict[str, tuple[str, str, bool]] = {
    "rainfall": ("recent rainfall", " mm", True),
    "rainfall_mm_sum_7d": ("rain in the last 7 days", " mm", True),
    "rainfall_mm_sum_14d": ("rain in the last 2 weeks", " mm", True),
    "rainfall_mm_sum_30d": ("rain in the last month", " mm", True),
    "Rainfall_mm": ("rain in the last month", " mm", True),
    "humidity": ("humidity", "%", True),
    "Humidity": ("humidity", "%", True),
    "humidity_pct_mean_14d": ("humidity over the last 2 weeks", "%", True),
    "humidity_pct_mean_7d": ("humidity over the last week", "%", True),
    "temperature": ("temperature", "°C", True),
    "Temperature_C": ("temperature", "°C", True),
    "temp_c_mean_14d": ("average temperature over the last 2 weeks", "°C", True),
    "temp_c_mean_7d": ("average temperature over the last week", "°C", True),
    "ph": ("soil acidity (pH)", "", True),
    "Soil_pH": ("soil acidity (pH)", "", True),
    "Soil_Moisture": ("soil moisture", "%", True),
    "N": ("nitrogen in the soil", "", False),
    "P": ("phosphorus in the soil", "", False),
    "K": ("potassium in the soil", "", False),
    "ndvi_trend": ("crop greenness trend from satellite", "", False),
}

_FACTOR_RE = re.compile(r"([A-Za-z_0-9]+) \((-?[\d.]+), (?:increases|decreases) the result\)")
_LIST_RE = re.compile(r"The biggest (?:contributing )?factors behind this (.+?) were: (.+?)(?:\.(?:\s|$))", re.S)

# Disease risk level -> what to actually do about it. Reuses
# disease_risk_scoring.RISK_ACTION directly (not a second copy) so the
# Advice tab's wording and the disease-scan result's wording never drift
# apart. "What mattered most" alone restates sensor readings with no
# action attached -- this is what makes the sentence actually useful to
# act on, not just read.
_DISEASE_ACTION = RISK_ACTION

# Standard agronomic soil-pH bands (topsoil, most field crops) -- lets a
# farmer who doesn't know what "pH 8.0" means see a verdict instead of a
# bare number. Deliberately conservative language ("most crops"): exact
# tolerance varies by crop, which this app doesn't model per-crop yet.
_PH_BANDS = [
    (5.5, "strongly acidic — can limit nutrient uptake for most crops; liming may help"),
    (6.5, "slightly acidic — fine for most crops"),
    (7.3, "near neutral — good for most crops"),
    (8.5, "slightly alkaline — fine for most crops, but may reduce iron/zinc availability"),
    (float("inf"), "strongly alkaline — can limit nutrient uptake; adding organic matter or gypsum may help"),
]


def _ph_verdict(ph: float) -> str:
    for upper, verdict in _PH_BANDS:
        if ph < upper:
            return verdict
    return _PH_BANDS[-1][1]


_WB_PARA_RE = re.compile(
    r"Predicted irrigation need: (\w+) \((?:soil moisture ([\d.]+)%)?.*?\)\. Water balance: "
    r"ET0=([\d.]+)mm/day, crop ETc=([\d.]+)mm/day over (\d+) days minus ([\d.]+)mm rainfall received "
    r"= (-?[\d.]+)mm net deficit -> ([\d.]+)mm recommended\.",
    re.S,
)


def _plain_water_balance(match: re.Match) -> str:
    """Same rewrite as plain_irrigation(), factored out so plain_paragraph
    can apply it to the irrigation paragraph inside a combined Advisory
    body -- previously only the standalone irrigation endpoint got this
    treatment, so this exact sentence (ET0/ETc/"net deficit") reached
    farmers verbatim every time via the Advice tab."""
    _need, moisture, _et0, etc, days, rain, _deficit, rec = match.groups()
    total = float(etc) * int(days)
    return (
        f"Your crop needs about {total:.0f} mm of water over the next {days} days. "
        f"About {float(rain):.0f} mm of rain has fallen, so about {float(rec):.0f} mm of "
        f"watering is recommended."
        + (f" Soil moisture is {float(moisture):.0f}%." if moisture else "")
    )


def _phrase(key: str, value: str) -> str:
    label, unit, show = _FEATURES.get(key, (key.replace("_", " "), "", True))
    if not show:
        return label
    try:
        num = float(value)
        text = f"{num:.0f}" if abs(num) >= 100 or num == int(num) else f"{num:.1f}"
    except ValueError:
        return f"{label} is {value}{unit}"
    phrase = f"{label} is {text}{unit}"
    if key in ("ph", "Soil_pH"):
        phrase += f" ({_ph_verdict(num)})"
    return phrase


def _factors(listing: str) -> str:
    parts = [_phrase(k, v) for k, v in _FACTOR_RE.findall(listing)]
    return "; ".join(parts) if parts else listing


def plain_paragraph(paragraph: str, drop_regional_caveat: bool = False) -> str:
    """Rewrites one explanation paragraph; unknown text passes through."""
    para = paragraph.strip()
    if drop_regional_caveat:
        para = re.sub(r"\s*Caveat: .*$", "", para, flags=re.S)

    # Irrigation's water-balance sentence has its own dedicated format
    # (not the generic "biggest factors" one) -- check it first, or this
    # paragraph passes through _LIST_RE untouched and a farmer sees
    # "ET0=5.2mm/day, crop ETc=6.8mm/day ... net deficit" verbatim.
    wb = _WB_PARA_RE.search(para)
    if wb:
        rest = para[wb.end():].strip()
        out = _plain_water_balance(wb)
        return f"{out} {rest}".strip()

    m = _LIST_RE.search(para)
    if not m:
        return para
    subject, listing = m.group(1), m.group(2)
    reasons = _factors(listing)
    rest = para[m.end():].strip()
    crop = re.match(r"recommendation of (\w+)", subject)
    if crop:
        head = f"Best crop for your field: {crop.group(1)}."
    elif "irrigation" in subject:
        level = subject.split()[0]
        head = f"Your field's need for watering is {level}."
    elif "disease" in subject:
        level = subject.split()[0]
        action = _DISEASE_ACTION.get(level, "")
        head = f"Chance of crop disease is {level}."
        out = f"{head} What mattered most: {reasons}."
        if action:
            out += f" What to do: {action}"
        return f"{out} {rest}".strip()
    else:
        head = f"{subject[0].upper()}{subject[1:]}."
    out = f"{head} What mattered most: {reasons}."
    return f"{out} {rest}".strip()


def plain_advisory(body: str, drop_regional_caveat: bool = False) -> str:
    paras = [p for p in re.split(r"\n\s*\n", body or "") if p.strip()]
    return "\n\n".join(plain_paragraph(p, drop_regional_caveat) for p in paras)


def plain_irrigation(rationale: str | None) -> str | None:
    if not rationale:
        return rationale
    m = _WB_PARA_RE.search(rationale)
    if not m:
        return rationale
    return _plain_water_balance(m)


# Rough bounding box of Karnataka: the crop model's regional check
# (models/regional_suitability.py, decisions/0016) is a hard-coded
# Bellary/Karnataka list, so its "not grown in your region" caveat is only
# meaningful for fields there.
_KARNATAKA = (11.5, 18.5, 74.0, 78.6)  # lat_min, lat_max, lon_min, lon_max


def in_karnataka(lat: float, lon: float) -> bool:
    return _KARNATAKA[0] <= lat <= _KARNATAKA[1] and _KARNATAKA[2] <= lon <= _KARNATAKA[3]
