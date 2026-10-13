"""A-06 내 참여, A-08 내 글, 그리고 무산 기록 문장(기획서 5.4)."""

import threading
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db import engine
from app.main import app

from .helpers import (
    insert_item,
    insert_reservation,
    insert_user,
    item_row,
    unique_location,
)

PAST = lambda: datetime.now(timezone.utc) - timedelta(minutes=1)  # noqa: E731


@pytest.fixture
def town():
    """같은 동네의 개설자와 사용자 생성 도구."""
    loc = unique_location()

    class T:
        owner = insert_user(loc, "개설자")

        def user(self, nickname="참여자"):
            return insert_user(loc, nickname)

        def item(self, **kw):
            return insert_item(self.owner.id, loc, **kw)

    return T()


def get(client: TestClient, user, path: str):
    return client.get(path, headers=user.headers)


# ---------- A-06 내 참여 ----------


def test_reservations_show_only_mine_newest_first(client: TestClient, town):
    me, other = town.user(), town.user()
    first, second, others = (
        town.item(title="첫째"),
        town.item(title="둘째"),
        town.item(title="남의"),
    )
    insert_reservation(first, me.id)
    insert_reservation(second, me.id)
    insert_reservation(others, other.id)

    body = get(client, me, "/me/reservations").json()
    assert [r["item"]["title"] for r in body["reservations"]] == ["둘째", "첫째"]
    r = body["reservations"][0]
    assert set(r) == {"reservation_id", "joined_at", "item"}
    assert set(r["item"]) == {
        "id", "type", "title", "owner_nickname", "price_per_slot", "deadline", "status", "pickup_note"
    }  # fmt: skip
    assert r["item"]["owner_nickname"] == "개설자"
    assert r["joined_at"].endswith("+09:00") and r["item"]["deadline"].endswith(
        "+09:00"
    )


@pytest.mark.parametrize(
    "fields, status, sees_note",
    [
        ({}, "OPEN", False),
        ({"status": "CONFIRMED", "filled_slots": 3}, "CONFIRMED", True),
        ({"status": "CANCELED"}, "CANCELED", False),
        ({"status": "FAILED"}, "FAILED", False),
        ({"deadline": PAST()}, "FAILED", False),  # 저장값은 OPEN, 마감이 지남
    ],
    ids=["open", "confirmed", "canceled", "failed", "open_but_expired"],
)
def test_pickup_note_only_when_confirmed(
    client: TestClient, town, fields, status, sees_note
):
    me = town.user()
    insert_reservation(town.item(total_slots=3, **fields), me.id)
    [r] = get(client, me, "/me/reservations").json()["reservations"]
    assert r["item"]["status"] == status
    assert r["item"]["pickup_note"] == ("메모" if sees_note else None)


def test_pickup_note_appears_after_the_last_slot_is_joined(client: TestClient, town):
    """성사 전에는 어느 응답에도 없던 메모가 마지막 몫이 차는 순간 참여자에게 열린다."""
    item_id = town.item(total_slots=1)
    me = town.user()
    assert "메모" not in get(client, me, "/me/reservations").text
    assert client.post(f"/items/{item_id}/join", headers=me.headers).status_code == 201
    [r] = get(client, me, "/me/reservations").json()["reservations"]
    assert (r["item"]["status"], r["item"]["pickup_note"]) == ("CONFIRMED", "메모")


def test_other_participants_cannot_see_the_note_before_confirmation(
    client: TestClient, town
):
    item_id = town.item(total_slots=3)
    a, b = town.user(), town.user()
    insert_reservation(item_id, a.id)
    insert_reservation(item_id, b.id)
    assert "메모" not in get(client, a, "/me/reservations").text


def test_reservations_empty_and_requires_login(client: TestClient, town):
    assert get(client, town.user(), "/me/reservations").json() == {"reservations": []}
    res = client.get("/me/reservations")
    assert (res.status_code, res.json()["code"]) == (401, "UNAUTHORIZED")


# ---------- A-08 내 글 ----------


def test_my_items_with_participants_and_owner_share(client: TestClient, town):
    a, b = town.user("라면왕"), town.user("자취생")
    mine = town.item(title="내 글", total_slots=5, total_price=25_000, filled_slots=2)
    insert_reservation(mine, a.id)
    insert_reservation(mine, b.id)
    other_owner = insert_user(unique_location(), "다른 개설자")
    insert_item(other_owner.id, unique_location(), title="남의 글")

    [item] = get(client, town.owner, "/me/items").json()["items"]
    assert item["title"] == "내 글"
    assert (item["filled_slots"], item["total_slots"]) == (2, 5)
    assert (item["total_price"], item["price_per_slot"], item["owner_share"]) == (
        25_000,
        4_160,
        4_200,
    )
    assert item["pickup_note"] == "메모"  # 개설자에게는 성사 전에도 항상 보인다
    assert [p["nickname"] for p in item["participants"]] == [
        "라면왕",
        "자취생",
    ]  # 신청 순서
    assert all(
        set(p) == {"reservation_id", "nickname", "joined_at"}
        for p in item["participants"]
    )  # 이메일·사용자 id는 안 나간다(신청 id만)
    assert "@" not in str(item)


def test_my_items_status_and_order(client: TestClient, town):
    town.item(title="오래된 글", status="CANCELED")
    town.item(title="새 글")
    town.item(title="마감 지난 글", deadline=PAST())
    items = get(client, town.owner, "/me/items").json()["items"]
    assert [i["title"] for i in items] == [
        "마감 지난 글",
        "새 글",
        "오래된 글",
    ]  # 최신순
    assert {i["title"]: i["status"] for i in items} == {
        "마감 지난 글": "FAILED", "새 글": "OPEN", "오래된 글": "CANCELED"
    }  # fmt: skip


def test_my_items_empty_and_requires_login(client: TestClient, town):
    assert get(client, town.user(), "/me/items").json() == {"items": []}
    assert client.get("/me/items").json()["code"] == "UNAUTHORIZED"


# ---------- 무산 기록 (기획서 5.4) ----------


@pytest.mark.parametrize("path", ["/me/items", "/me/reservations"])
def test_recording_marks_only_expired_open_items(client: TestClient, town, path):
    expired = town.item(deadline=PAST())
    live = town.item()
    confirmed_past = town.item(status="CONFIRMED", filled_slots=3, deadline=PAST())
    other_users_expired = insert_item(
        insert_user(unique_location()).id, unique_location(), deadline=PAST()
    )

    assert get(client, town.owner, path).status_code == 200
    assert item_row(expired).status == "FAILED"
    assert (
        item_row(other_users_expired).status == "FAILED"
    )  # 문장은 전체에 대해 한 번에 기록한다
    assert item_row(live).status == "OPEN"
    assert item_row(confirmed_past).status == "CONFIRMED"  # 성사된 글은 건드리지 않는다


def test_recording_is_idempotent(client: TestClient, town):
    town.item(deadline=PAST())
    first = get(client, town.owner, "/me/items").json()
    second = get(client, town.owner, "/me/items").json()
    assert first == second


def test_locked_rows_are_skipped_not_waited_for(client: TestClient, town):
    """다른 요청이 잡고 있는 행은 기다리지 않고 건너뛴다(SKIP LOCKED).
    그 사이 응답은 display_status가 FAILED로 보정하고, 잠금이 풀린 뒤 다음 조회 때 기록된다."""
    item_id = town.item(deadline=PAST())
    result: dict = {}

    def request():
        result["res"] = get(TestClient(app), town.owner, "/me/items")

    with engine.connect() as locker:
        locker.execute(
            text("SELECT id FROM items WHERE id = :id FOR UPDATE"), {"id": item_id}
        )
        t = threading.Thread(target=request)
        t.start()
        t.join(timeout=10)
        blocked = t.is_alive()
        status_while_locked = item_row(item_id).status
        locker.rollback()  # 잠금 해제
    t.join(timeout=10)

    assert not blocked, "잠긴 행 때문에 요청이 멈췄습니다(SKIP LOCKED가 필요)"
    assert result["res"].status_code == 200
    assert result["res"].json()["items"][0]["status"] == "FAILED"  # 표시는 이미 보정됨
    assert status_while_locked == "OPEN"  # 잠겨 있어서 아직 기록되지 않았다

    get(client, town.owner, "/me/items")
    assert item_row(item_id).status == "FAILED"  # 잠금이 풀린 뒤에는 기록된다


def test_recording_failure_does_not_fail_the_request(
    client: TestClient, town, monkeypatch
):
    item_id = town.item(deadline=PAST())
    monkeypatch.setattr(
        "app.items.FAIL_SQL", text("SELECT * FROM no_such_table_for_test")
    )

    res = get(client, town.owner, "/me/items")
    assert res.status_code == 200  # 기록이 깨져도 조회는 된다
    assert res.json()["items"][0]["status"] == "FAILED"  # 표시는 보정된다
    assert item_row(item_id).status == "OPEN"
