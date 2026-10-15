"""Pre-check for leaf-disease photos: is this plausibly a plant photo at all?

Why this exists (Module 39, found live): the disease CNN is a closed-set
classifier over PlantVillage's 38 classes. Given a photo of a bed sheet it
still answered "Tomato: Early blight, severe, confidence 100%" -- softmax
confidence is not evidence that the input is a leaf. So before the photo
reaches the CNN we require a minimum share of plant-coloured pixels (green /
yellow-green foliage, plus brown-yellow lesion tones *next to* green). It only
needs Pillow + numpy, so it stays in the main API process (torch is kept out
of it, decisions/0019).

This is a coarse colour + texture test: it rejects white sheets, walls, skin,
screens, sky, floors, and flat/solid green images (a green screen has no leaf
texture). It cannot catch a textured green fake such as a patterned cloth. The
response says how to retake the photo instead of guessing.
"""
import io

import numpy as np
from PIL import Image

#: Fraction of pixels that must look like living foliage.
MIN_PLANT_FRACTION = 0.10
#: Lesion colours count as plant only next to this much real foliage. Was 0.08, which
#: rejected a badly diseased apple-scab leaf (5% green, 9% lesions); 0.04 keeps skin/wood out.
_MIN_GREEN_FOR_LESIONS = 0.04
#: Minimum tonal variation / edge share; rejects flat colour images.
MIN_LUM_STD = 0.04
MIN_EDGE_FRACTION = 0.02


def plant_stats(image_bytes: bytes) -> dict[str, float]:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img.thumbnail((256, 256))
    rgb = np.asarray(img, dtype=np.float32)
    hsv = np.asarray(img.convert("HSV"), dtype=np.float32)
    hue = hsv[..., 0] * 360.0 / 255.0
    sat = hsv[..., 1] / 255.0
    val = hsv[..., 2] / 255.0
    # yellow-green .. green .. blue-green foliage
    green = (hue >= 45) & (hue <= 165) & (sat >= 0.20) & (val >= 0.12)
    # brown / orange-yellow lesions and dry leaf tissue
    lesion = (hue >= 15) & (hue < 45) & (sat >= 0.30) & (val >= 0.15)
    green_frac = float(green.mean())
    lesion_frac = float(lesion.mean())

    # Check for synthetic text/thin-lines or fragmented matrix code:
    # 3x3 erosion checks if green pixels form contiguous spatial masses (like a real leaf)
    # vs thin 1-2px computer text lines or scattered noise
    if green.shape[0] > 2 and green.shape[1] > 2:
        eroded_green = green[1:-1, 1:-1] & green[:-2, 1:-1] & green[2:, 1:-1] & green[1:-1, :-2] & green[1:-1, 2:]
        eroded_green_frac = float(eroded_green.mean())
    else:
        eroded_green_frac = 0.0

    # Pure synthetic digital greens (e.g. #00FF00 where R=0 and B=0)
    synthetic_green = green & (rgb[..., 0] <= 15) & (rgb[..., 2] <= 15) & (rgb[..., 1] >= 180)
    synthetic_frac = float(synthetic_green.mean())

    # lesions only count when there is real foliage around them
    plant_frac = green_frac + (lesion_frac if green_frac >= _MIN_GREEN_FOR_LESIONS else 0.0)

    # A real leaf photo has veins, edges and tonal variation; a green screen,
    # green wall or solid-colour image is flat. Measure luminance spread and
    # the share of pixels sitting on an edge.
    lum = np.asarray(img.convert("L"), dtype=np.float32) / 255.0
    lum_std = float(lum.std())
    gx = np.abs(np.diff(lum, axis=1))[:-1, :]
    gy = np.abs(np.diff(lum, axis=0))[:, :-1]
    edge_frac = float(((gx + gy) > 0.04).mean())
    return {
        "green": green_frac,
        "eroded_green": eroded_green_frac,
        "synthetic": synthetic_frac,
        "lesion": lesion_frac,
        "plant": plant_frac,
        "lum_std": lum_std,
        "edge": edge_frac,
    }


def looks_like_plant_photo(image_bytes: bytes) -> bool:
    s = plant_stats(image_bytes)
    # Reject pure synthetic digital colors (e.g. hacker matrix green)
    if s["synthetic"] > 0.05 and s["synthetic"] > s["green"] * 0.4:
        return False
    # Reject disconnected text/lines (if green exists but is almost all thin edges, eroded is < 15% of green)
    if s["green"] >= 0.08 and s["eroded_green"] < s["green"] * 0.15:
        return False
    textured = s["lum_std"] >= MIN_LUM_STD and s["edge"] >= MIN_EDGE_FRACTION
    return s["plant"] >= MIN_PLANT_FRACTION and textured
