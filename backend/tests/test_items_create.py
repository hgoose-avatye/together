"""A-04 글 작성(같이사기). 개발용 Supabase DB에 실제로 쓴다."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.config import settings
from app.db import engine
from app.geo import haversine_km

from .conftest import make_user

KST = timezone(timedelta(hours=9))


@pytest.fixture(scope="module")
def shared_user(client: TestClient):
    """입력 검증처럼 사용자를 공유해도 되는 테스트용. bcrypt가 느려서 매번 만들지 않는다."""
    return make_user(client)


def in_hours(hours: float) -> str:
    return (datetime.now(KST) + timedelta(hours=hours)).isoformat()


def item_payload(**override) -> dict:
    payload = {
        "type": "GROUP_BUY",
        "category": "FRUIT_VEG",
        "title": "샤인머스켓 2kg 나눠요",
        "total_slots": 5,
        "total_price": 25_000,
        "deadline": in_hours(24),
        "pickup_note": "망원역 2번 출구, 10/13 19시, 오픈채팅 https://open.kakao.com/x",
        "product_url": "https://example.com/product/123",
    }
    payload.update(override)
    return payload


def db_item(item_id: int):
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT * FROM items WHERE id = :id"), {"id": item_id}
        ).one()


def own_image_url(name: str | None = None, ext: str = "webp") -> str:
    return (
        f"{settings.supabase_url}/storage/v1/object/public/{settings.supabase_bucket}/"
        f"{name or uuid.uuid4()}.{ext}"
    )


# ---------- 성공 ----------


def test_create_item_success(client: TestClient):
    me = make_user(client, nickname="망원동자취생")
    res = client.post("/items", json=item_payload(), headers=me.headers)
    assert res.status_code == 201, res.text
    body = res.json()

    # 나 포함 6명, 25,000원 → 참여자 4,160원, 개설자 4,200원 (합계 25,000원)
    assert body["price_per_slot"] == 4_160
    assert body["owner_share"] == 4_200
    assert (
        body["price_per_slot"] * body["total_slots"] + body["owner_share"]
        == body["total_price"]
    )

    assert body["owner_nickname"] == "망원동자취생"
    assert (
        body["total_slots"] == 5
        and body["filled_slots"] == 0
        and body["remaining_slots"] == 5
    )
    assert body["status"] == "OPEN"
    assert body["is_mine"] is True and body["is_joined"] is False
    assert body["distance_km"] == 0.0  # 위치를 안 보냈으니 내 위치와 같다
    assert body["pickup_note"].startswith("망원역")
    assert body["deadline"].endswith("+09:00")  # 오프셋이 붙은 한국 시간


def test_create_item_is_saved_with_server_decided_values(client: TestClient):
    me = make_user(client, lat=37.5563, lng=126.9019)
    body = client.post(
        "/items",
        json=item_payload(total_price=10_000, total_slots=2),
        headers=me.headers,
    ).json()
    row = db_item(body["id"])

    assert row.owner_id == me.id
    assert (row.price_per_slot, row.total_price, row.total_slots) == (3_330, 10_000, 2)
    assert (
        row.filled_slots == 0 and row.status == "OPEN" and row.category == "FRUIT_VEG"
    )
    assert (float(row.lat), float(row.lng)) == (37.56, 126.90)  # 내 저장 위치가 기본값


def test_demo_one_slot_item(client: TestClient):
    """데모 시나리오 3번: 나 포함 2명(몫 1개)."""
    me = make_user(client)
    body = client.post(
        "/items",
        json=item_payload(total_slots=1, total_price=10_000),
        headers=me.headers,
    ).json()
    assert (body["price_per_slot"], body["owner_share"]) == (5_000, 5_000)


def test_zero_price_is_allowed(client: TestClient):
    me = make_user(client)
    res = client.post("/items", json=item_payload(total_price=0), headers=me.headers)
    assert res.status_code == 201
    assert (res.json()["price_per_slot"], res.json()["owner_share"]) == (0, 0)


def test_category_defaults_to_etc_and_optional_fields_can_be_omitted(
    client: TestClient,
):
    me = make_user(client)
    payload = item_payload()
    for key in ("category", "product_url"):
        del payload[key]
    body = client.post("/items", json=payload, headers=me.headers).json()
    assert (
        body["category"] == "ETC"
        and body["product_url"] is None
        and body["image_url"] is None
    )


def test_custom_location_is_rounded_and_distance_is_computed(client: TestClient):
    me = make_user(client, lat=37.5563, lng=126.9019)
    res = client.post(
        "/items", json=item_payload(lat=37.4979, lng=127.0276), headers=me.headers
    )
    assert res.status_code == 201
    row = db_item(res.json()["id"])
    assert (float(row.lat), float(row.lng)) == (37.50, 127.03)  # 소수점 2자리로 반올림
    # 거리는 내 저장 위치(37.56, 126.90)와 글 위치(37.50, 127.03) 사이다.
    assert (
        res.json()["distance_km"]
        == round(haversine_km(37.56, 126.90, 37.50, 127.03), 1)
        == 13.3
    )


def test_owner_id_in_body_is_ignored(client: TestClient):
    me, other = make_user(client), make_user(client)
    res = client.post(
        "/items", json=item_payload(owner_id=other.id), headers=me.headers
    )
    assert res.status_code == 201
    assert db_item(res.json()["id"]).owner_id == me.id


def test_valid_links_and_own_image_url_are_accepted(client: TestClient):
    me = make_user(client)
    image = own_image_url()
    res = client.post(
        "/items",
        json=item_payload(product_url="http://example.com/a?b=1", image_url=image),
        headers=me.headers,
    )
    assert res.status_code == 201
    assert res.json()["image_url"] == image


def test_empty_optional_strings_become_null(client: TestClient):
    me = make_user(client)
    res = client.post(
        "/items", json=item_payload(product_url="", image_url=""), headers=me.headers
    )
    assert res.status_code == 201
    assert res.json()["product_url"] is None and res.json()["image_url"] is None


# ---------- 인증 ----------


def test_requires_login(client: TestClient):
    res = client.post("/items", json=item_payload())
    assert res.status_code == 401
    assert res.json()["code"] == "UNAUTHORIZED"


# ---------- 입력 오류 ----------

BAD_URLS = [
    "ftp://example.com/x",
    "javascript:alert(1)",
    "not a url",
    "example.com/no-scheme",
]
BAD_IMAGES = [
    "https://evil.example.com/storage/v1/object/public/images/"
    + "0" * 8
    + "-0000-0000-0000-"
    + "0" * 12
    + ".webp",
    f"{settings.supabase_url}/storage/v1/object/public/other-bucket/{uuid.uuid4()}.webp",  # 다른 버킷
    f"{settings.supabase_url}/storage/v1/object/public/{settings.supabase_bucket}/not-a-uuid.webp",
    f"{settings.supabase_url}/storage/v1/object/public/{settings.supabase_bucket}/{uuid.uuid4()}.gif",
    f"{settings.supabase_url}/storage/v1/object/public/{settings.supabase_bucket}/{uuid.uuid4()}.webp?x=1",
    f"{settings.supabase_url}.evil.com/storage/v1/object/public/{settings.supabase_bucket}/{uuid.uuid4()}.webp",
]


@pytest.mark.parametrize(
    "override, field",
    [
        ({"type": "X"}, "type"),
        ({"category": "TOYS"}, "category"),
        ({"title": ""}, "title"),
        ({"title": "   "}, "title"),
        ({"title": "가" * 51}, "title"),
        ({"total_slots": 0}, "total_slots"),
        ({"total_slots": 21}, "total_slots"),
        ({"total_price": -1}, "total_price"),
        ({"total_price": 1_000_001}, "total_price"),
        ({"deadline": in_hours(-1)}, "deadline"),  # 과거
        ({"deadline": in_hours(24 * 30 + 1)}, "deadline"),  # 30일 초과
        ({"deadline": "2099-01-01T00:00:00"}, "deadline"),  # 시간대 없음
        ({"deadline": "내일"}, "deadline"),
        ({"pickup_note": ""}, "pickup_note"),
        ({"pickup_note": "가" * 201}, "pickup_note"),
        ({"lat": 91, "lng": 127}, "lat"),
        ({"lat": 37.5, "lng": 181}, "lng"),
        ({"lat": 37.5}, "lng"),  # 위도만 보냄
        *[({"product_url": u}, "product_url") for u in BAD_URLS],
        *[({"image_url": u}, "image_url") for u in BAD_IMAGES],
    ],
)
def test_invalid_input_is_400_with_field(client: TestClient, shared_user, override, field):
    me = shared_user
    res = client.post("/items", json=item_payload(**override), headers=me.headers)
    assert res.status_code == 400, res.text
    body = res.json()
    assert body["code"] == "INVALID_INPUT"
    assert body["field"] == field
    assert body["message"]


def test_boundary_values_are_accepted(client: TestClient, shared_user):
    me = shared_user
    for override in (
        {"total_slots": 1},
        {"total_slots": 20},
        {"total_price": 1_000_000},
        {"title": "가" * 50},
        {"pickup_note": "가" * 200},
        {"deadline": in_hours(24 * 30 - 1)},
    ):
        res = client.post("/items", json=item_payload(**override), headers=me.headers)
        assert res.status_code == 201, (override, res.text)


def test_rejected_requests_leave_no_rows(client: TestClient):
    me = make_user(client)
    client.post("/items", json=item_payload(title=""), headers=me.headers)
    with engine.connect() as conn:
        count = conn.execute(
            text("SELECT count(*) FROM items WHERE owner_id = :id"), {"id": me.id}
        ).scalar()
    assert count == 0
