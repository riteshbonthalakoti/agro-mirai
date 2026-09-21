"""Module 39: the leaf gate must reject non-plant photos (a bed sheet was
diagnosed as 'Tomato: Early blight, severe, 100%') yet accept real leaf photos."""
import glob
import io

import numpy as np
import pytest
from PIL import Image

from agro_mirai.api.leaf_gate import looks_like_plant_photo


def _png(rgb):
    arr = np.zeros((200, 200, 3), dtype="uint8")
    arr[...] = rgb
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, "PNG")
    return buf.getvalue()


@pytest.mark.parametrize("rgb", [(240, 240, 240), (225, 220, 210), (170, 190, 235), (235, 190, 200), (205, 165, 135), (25, 25, 25)])
def test_non_plant_photos_rejected(rgb):
    assert not looks_like_plant_photo(_png(rgb))


def _to_png(arr):
    buf = io.BytesIO()
    Image.fromarray(arr.astype("uint8")).save(buf, "PNG")
    return buf.getvalue()


def test_flat_green_screen_rejected():
    # Found live: a solid green image (Google "green screen") passed the
    # colour test and was "diagnosed" with 100% confidence.
    assert not looks_like_plant_photo(_png((60, 140, 50)))
    assert not looks_like_plant_photo(_png((0, 177, 64)))


def test_smooth_green_gradient_rejected():
    x = np.linspace(0, 1, 200)
    arr = np.zeros((200, 200, 3))
    arr[..., 0] = 40 + 20 * x
    arr[..., 1] = 130 + 20 * x
    arr[..., 2] = 40
    assert not looks_like_plant_photo(_to_png(arr))


def test_textured_foliage_accepted():
    rng = np.random.default_rng(0)
    arr = np.zeros((200, 200, 3))
    arr[..., 0] = 50
    arr[..., 1] = 130
    arr[..., 2] = 40
    arr += rng.normal(0, 30, arr.shape)  # veins / shading / grain
    arr[:, ::20] *= 0.4  # vein-like dark lines
    assert looks_like_plant_photo(_to_png(np.clip(arr, 0, 255)))


def test_real_leaf_samples_accepted():
    files = [f for f in glob.glob("AGRO_MIRAI_DEMO/samples/*.jpg") if "not_a_leaf" not in f]
    if not files:
        pytest.skip("demo samples not present")
    for f in files:
        assert looks_like_plant_photo(open(f, "rb").read()), f
