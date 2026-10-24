import io
import os
import sys
import tempfile
from pathlib import Path

import pytest

# Isolated, offline configuration for every test run (set before the app is imported).
_TMP = tempfile.mkdtemp(prefix="cip_tests_")
os.environ["DEMO_MODE"] = "true"
os.environ["STORAGE_DIR"] = _TMP
os.environ["GROQ_API_KEY"] = ""
os.environ["HF_TOKEN"] = ""
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

from app.config import get_settings  # noqa: E402

get_settings.cache_clear()

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    return TestClient(app)


def make_image(size=(640, 480), color=None, fmt="JPEG", pattern=True) -> bytes:
    img = Image.new("RGB", size, color or (150, 140, 120))
    if pattern:
        # draw stripes so the image is not "blurry/low contrast"
        px = img.load()
        for x in range(0, size[0], 8):
            for y in range(size[1]):
                px[x, y] = (20, 20, 20)
    buf = io.BytesIO()
    img.save(buf, fmt)
    return buf.getvalue()


@pytest.fixture
def jpeg():
    return make_image()
