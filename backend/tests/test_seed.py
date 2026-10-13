"""시드 스크립트의 DB를 쓰지 않는 부분: 만든 그림이 업로드 규칙을 지키는지, 동네 목록이 프론트와 같은지."""

import importlib.util
import re
from pathlib import Path

from app.uploads import MAX_BYTES, detect_type

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("seed", ROOT / "backend/scripts/seed.py")
seed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(seed)


def test_generated_pictures_are_valid_uploads():
    for rgb in seed.COLORS:
        data = seed.png(320, 240, rgb)
        assert detect_type(data[:12]) == ("png", "image/png") and len(data) <= MAX_BYTES


def test_hoods_match_frontend_list():
    ts = (ROOT / "frontend/src/neighborhoods.ts").read_text(encoding="utf-8")
    front = [(n, float(a), float(b)) for n, a, b in re.findall(r"name: '([^']+)', lat: ([\d.]+), lng: ([\d.]+)", ts)]
    assert front == seed.HOODS
