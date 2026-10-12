"""에러 코드 표(app/errors.py)가 기획서 8장과 같은지, 응답 형식이 약속대로인지 검사한다."""

import re
from decimal import Decimal
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.errors import ERRORS, AppError, register_error_handlers
from app.schemas import round_coord

SPEC = Path(__file__).resolve().parents[2] / "gachi-spec.md"


def spec_error_rows() -> dict[str, tuple[int, str]]:
    section = (
        SPEC.read_text(encoding="utf-8")
        .split("## 8. 에러 코드 기준")[1]
        .split("## 9.")[0]
    )
    rows = {}
    for line in section.splitlines():
        m = re.match(r"^\| `([A-Z_]+)` \| (\d{3}) \|", line)
        if m:
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            rows[m.group(1)] = (int(m.group(2)), cells[4])
    return rows


def test_error_table_matches_spec():
    spec = spec_error_rows()
    assert set(spec) == set(ERRORS), "기획서 8장과 app/errors.py의 코드 목록이 다릅니다"
    for code, (status, message) in spec.items():
        assert ERRORS[code][0] == status, f"{code}의 HTTP 상태가 기획서와 다릅니다"
        if code != "INVALID_INPUT":  # 이 코드의 문구는 상황마다 직접 쓴다
            assert ERRORS[code][1] == message, f"{code}의 화면 문구가 기획서와 다릅니다"


def make_app() -> TestClient:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/boom")
    def boom():
        raise AppError("SLOTS_FULL")

    @app.get("/field")
    def field():
        raise AppError("INVALID_INPUT", "마감 시각은 지금 이후여야 해요", "deadline")

    return TestClient(app)


def test_error_body_has_only_code_and_message():
    res = make_app().get("/boom")
    assert res.status_code == 409
    assert res.json() == {"code": "SLOTS_FULL", "message": "방금 몫이 모두 찼어요"}


def test_invalid_input_body_has_field():
    res = make_app().get("/field")
    assert res.status_code == 400
    assert res.json() == {
        "code": "INVALID_INPUT",
        "message": "마감 시각은 지금 이후여야 해요",
        "field": "deadline",
    }


def test_unknown_route_uses_error_format():
    res = make_app().get("/nope")
    assert res.status_code == 404
    assert res.json()["code"] == "NOT_FOUND"


def test_round_coord():
    assert round_coord(37.5563) == Decimal("37.56")
    assert round_coord(126.9019) == Decimal("126.90")
    assert round_coord(37.555) == Decimal("37.56")  # float 오차 없이 반올림
    assert round_coord(-37.555) == Decimal("-37.56")
    assert round_coord(37) == Decimal("37.00")
