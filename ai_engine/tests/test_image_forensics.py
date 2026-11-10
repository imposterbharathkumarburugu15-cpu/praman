import io
import pytest
import numpy as np
from PIL import Image

from ai_engine.forensics import ImageForensicsAnalyzer


@pytest.fixture
def forensics():
    return ImageForensicsAnalyzer()


def test_pristine_image_tamper_evaluation(forensics):
    """Verifies pristine uniform image is not falsely flagged as tampered."""
    # Create smooth natural-like gradient image
    arr = np.zeros((256, 256, 3), dtype=np.uint8)
    for y in range(256):
        arr[y, :, 0] = y // 2
        arr[y, :, 1] = 120
        arr[y, :, 2] = 80
    img = Image.fromarray(arr)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)

    res = forensics.evaluate_tamper(buf.getvalue())

    assert "ela_variance" in res
    assert "noise_variance" in res
    assert "is_tamper_suspected" in res
    assert res["is_tamper_suspected"] is False
    assert res["validation_status"] == "FORMALLY_EVALUATED"
    assert res["autonomous_action_allowed"] is False


def test_spliced_image_detected(forensics):
    """Verifies digital splice with disparate noise profile triggers is_tamper_suspected."""
    base = np.zeros((300, 300, 3), dtype=np.uint8) + 120
    # Paste high-noise spliced patch into the center
    splice_noise = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
    base[100:200, 100:200] = splice_noise

    img = Image.fromarray(base)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)

    res = forensics.evaluate_tamper(buf.getvalue())

    assert res["is_tamper_suspected"] is True
    assert res["noise_disparity_ratio"] > 15.0
    # Invariant: even with detected splice, autonomous action is prohibited!
    assert res["autonomous_action_allowed"] is False


def test_ela_computation_positive_variance(forensics):
    """Verifies Error Level Analysis produces real positive error variance on textured image."""
    arr = np.random.randint(50, 200, (128, 128, 3), dtype=np.uint8)
    img = Image.fromarray(arr)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)

    res = forensics.evaluate_tamper(buf.getvalue())
    assert res["ela_variance"] > 0.0
    assert res["noise_variance"] > 0.0
