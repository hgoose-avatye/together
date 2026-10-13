"""나눔 묶음: 나눔 글 작성(A-04 SHARE), 목록 탭, 신청 즉시 성사 (기획서 5.3, 5.4)."""

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.config import settings
from app.db import engine

from .helpers import insert_item, insert_user, item_row, unique_location

KST = timezone(timedelta(hours=9))


def image() -> str:
    return f"{settings.supabase_url}/storage/v1/object/public/{settings.supabase_bucket}/{uuid.uuid4()}.webp"


def today() -> date:
    return datetime.now(KST).date()


def share(**override) -> dict:
    body = {
        "type": "SHARE",
        "title": "두부 반 모, 내일까지",
        "expiry_date": today().isoformat(),
        "pickup_note": "망원동 ○○빌라 앞, 오늘 21시 이후",
        "image_url": image(),
    }
    body.update(override)
    return body


@pytest.fixture
def me():
    return insert_user(unique_location(), "나눔이")


def create(client, user, **kw):
    return client.post("/items", json=share(**kw), headers=user.headers)


def test_share_create_sets_server_values(client: TestClient, me):
    # total_slots, total_price, deadline, price는 보내도 서버가 정한다
    res = create(client, me, total_slots=7, total_price=99_999, deadline="2099-01-01T00:00:00+09:00", price_per_slot=500)
    assert res.status_code == 201, res.text
    b = res.json()
    assert (b["type"], b["total_slots"], b["total_price"], b["price_per_slot"], b["owner_share"]) == ("SHARE", 1, 0, 0, 0)
    expected = datetime.combine(today() + timedelta(days=1), datetime.min.time(), KST)
    assert datetime.fromisoformat(b["deadline"]) == expected  # 유통기한 다음 날 00:00 KST
    assert b["image_url"] and b["pickup_note"]
    row = item_row(b["id"])
    assert (row.total_slots, row.total_price, row.price_per_slot, row.type) == (1, 0, 0, "SHARE")


def test_share_deadline_is_next_midnight_for_future_date(client: TestClient, me):
    d = today() + timedelta(days=5)
    b = create(client, me, expiry_date=d.isoformat()).json()
    assert b["deadline"].startswith((d + timedelta(days=1)).isoformat() + "T00:00:00")
    assert b["deadline"].endswith("+09:00")


@pytest.mark.parametrize(
    "override, field",
    [
        ({"image_url": None}, "image_url"),
        ({"image_url": ""}, "image_url"),
        ({"image_url": "https://evil.example.com/a.webp"}, "image_url"),
        ({"expiry_date": None}, "expiry_date"),
        ({"expiry_date": "내일"}, "expiry_date"),
        ({"expiry_date": (date.today() - timedelta(days=2)).isoformat()}, "expiry_date"),  # 이미 지남
        ({"expiry_date": (date.today() + timedelta(days=40)).isoformat()}, "expiry_date"),  # 30일 초과
        ({"product_url": "https://example.com/x"}, "product_url"),  # 나눔은 상품 링크를 받지 않는다
        ({"title": ""}, "title"),
        ({"pickup_note": ""}, "pickup_note"),
    ],
)
def test_share_invalid_input(client: TestClient, me, override, field):
    res = create(client, me, **override)
    assert (res.status_code, res.json()["code"], res.json().get("field")) == (400, "INVALID_INPUT", field)


def test_expiry_boundaries(client: TestClient, me):
    assert create(client, me, expiry_date=(today() + timedelta(days=30)).isoformat()).status_code == 201
    assert create(client, me, expiry_date=(today() + timedelta(days=31)).isoformat()).status_code == 400


def test_group_buy_still_requires_its_fields(client: TestClient, me):
    base = {"type": "GROUP_BUY", "title": "t", "pickup_note": "n"}
    for missing in ("total_slots", "total_price", "deadline"):
        body = {**base, "total_slots": 2, "total_price": 1000, "deadline": (datetime.now(KST) + timedelta(hours=3)).isoformat()}
        del body[missing]
        res = client.post("/items", json=body, headers=me.headers)
        assert (res.status_code, res.json().get("field")) == (400, missing)


def test_group_buy_accepts_optional_photo(client: TestClient, me):
    body = {"type": "GROUP_BUY", "title": "t", "total_slots": 2, "total_price": 1000, "pickup_note": "n",
            "deadline": (datetime.now(KST) + timedelta(hours=3)).isoformat(), "image_url": image()}
    res = client.post("/items", json=body, headers=me.headers)
    assert res.status_code == 201 and res.json()["image_url"] == body["image_url"]


def test_share_db_rule_blocks_share_without_photo():
    owner = insert_user(unique_location(), "제약")
    with pytest.raises(Exception), engine.begin() as conn:  # CHECK share_rule
        conn.execute(text(
            "INSERT INTO items (owner_id, type, title, total_slots, total_price, price_per_slot, deadline, lat, lng, pickup_note) "
            "VALUES (:o, 'SHARE', 't', 1, 0, 0, now() + interval '1 day', 37.5, 127, 'n')"), {"o": owner.id})


# ---------- 목록 탭과 신청 ----------


def test_share_tab_and_instant_confirmation(client: TestClient):
    loc = unique_location()
    owner, joiner = insert_user(loc, "개설자"), insert_user(loc, "받는이")
    created = client.post("/items", json=share(lat=loc[0], lng=loc[1]), headers=owner.headers).json()

    shares = client.get("/items", params={"type": "SHARE", "lat": loc[0], "lng": loc[1]}, headers=joiner.headers).json()["items"]
    assert [i["id"] for i in shares] == [created["id"]] and shares[0]["image_url"]
    assert client.get("/items", params={"type": "GROUP_BUY", "lat": loc[0], "lng": loc[1]}, headers=joiner.headers).json()["items"] == []

    res = client.post(f"/items/{created['id']}/join", headers=joiner.headers)
    assert res.status_code == 201 and res.json()["status"] == "CONFIRMED"  # 신청 즉시 성사
    [r] = client.get("/me/reservations", headers=joiner.headers).json()["reservations"]
    assert (r["item"]["type"], r["item"]["price_per_slot"], r["item"]["pickup_note"]) == ("SHARE", 0, "망원동 ○○빌라 앞, 오늘 21시 이후")


def test_share_closes_at_next_midnight(client: TestClient):
    loc = unique_location()
    owner, late, early = insert_user(loc), insert_user(loc), insert_user(loc)
    just_before = insert_item(owner.id, loc, type="SHARE", deadline=datetime.now(timezone.utc) + timedelta(seconds=40))
    just_after = insert_item(owner.id, loc, type="SHARE", deadline=datetime.now(timezone.utc) - timedelta(seconds=1))
    assert client.post(f"/items/{just_before}/join", headers=early.headers).status_code == 201
    res = client.post(f"/items/{just_after}/join", headers=late.headers)
    assert (res.status_code, res.json()["code"]) == (410, "EXPIRED")
