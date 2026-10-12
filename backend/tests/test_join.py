"""A-05 몫 신청. 순차적인 동작과 실패 원인 판정을 검사한다. 동시 요청은 test_join_concurrency.py."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.join import Cause, classify_failure

from .helpers import (
    insert_item,
    insert_reservation,
    insert_user,
    item_row,
    reservation_count,
    unique_location,
)


def now() -> datetime:
    return datetime.now(timezone.utc)


def join(client: TestClient, user, item_id: int):
    return client.post(f"/items/{item_id}/join", headers=user.headers)


@pytest.fixture
def setup():
    """개설자 한 명과 같은 동네의 사용자 생성 도구."""
    loc = unique_location()
    owner = insert_user(loc, "개설자")

    class Ctx:
        location = loc

        def __init__(self):
            self.owner = owner

        def user(self, nickname="참여자"):
            return insert_user(loc, nickname)

        def item(self, **kw):
            return insert_item(owner.id, loc, **kw)

    return Ctx()


# ---------- 성공 ----------


def test_join_success(client: TestClient, setup):
    item_id = setup.item(total_slots=3)
    me = setup.user()
    res = join(client, me, item_id)

    assert res.status_code == 201, res.text
    body = res.json()
    assert set(body) == {
        "reservation_id", "item_id", "filled_slots", "total_slots", "remaining_slots", "status"
    }  # fmt: skip
    assert (body["item_id"], body["filled_slots"], body["total_slots"]) == (
        item_id,
        1,
        3,
    )
    assert (body["remaining_slots"], body["status"]) == (2, "OPEN")

    row = item_row(item_id)
    assert (row.filled_slots, row.status) == (1, "OPEN")
    assert reservation_count(item_id) == 1


def test_last_slot_confirms_the_item(client: TestClient, setup):
    item_id = setup.item(total_slots=1)
    res = join(client, setup.user(), item_id)
    assert res.status_code == 201
    assert (res.json()["status"], res.json()["remaining_slots"]) == ("CONFIRMED", 0)
    assert item_row(item_id).status == "CONFIRMED"

    # 성사된 글은 목록에서 사라진다
    other = setup.user()
    listed = client.get(
        "/items", params={"type": "GROUP_BUY"}, headers=other.headers
    ).json()
    assert item_id not in [i["id"] for i in listed["items"]]


def test_slots_fill_one_by_one_then_next_user_is_rejected(client: TestClient, setup):
    item_id = setup.item(total_slots=3)
    statuses = [join(client, setup.user(), item_id).json()["status"] for _ in range(3)]
    assert statuses == ["OPEN", "OPEN", "CONFIRMED"]  # 마지막 몫에서 성사

    late = join(client, setup.user(), item_id)
    assert late.status_code == 409
    assert late.json()["code"] == "SLOTS_FULL"
    row = item_row(item_id)
    assert (row.filled_slots, row.status) == (3, "CONFIRMED")  # 늘지 않았다
    assert reservation_count(item_id) == 3


def test_join_response_has_no_pickup_note(client: TestClient, setup):
    res = join(client, setup.user(), setup.item())
    assert "pickup_note" not in res.text


def test_join_shows_up_in_list_as_joined(client: TestClient, setup):
    item_id = setup.item(total_slots=3)
    me = setup.user()
    join(client, me, item_id)
    [item] = client.get(
        "/items", params={"type": "GROUP_BUY"}, headers=me.headers
    ).json()["items"]
    assert (
        item["id"],
        item["is_joined"],
        item["filled_slots"],
        item["remaining_slots"],
    ) == (item_id, True, 1, 2)


# ---------- 중복 신청 ----------


def test_second_join_by_same_user_is_rejected_and_rolled_back(
    client: TestClient, setup
):
    item_id = setup.item(total_slots=3)
    me = setup.user()
    assert join(client, me, item_id).status_code == 201

    again = join(client, me, item_id)
    assert again.status_code == 409
    assert again.json()["code"] == "ALREADY_JOINED"
    # UNIQUE 위반으로 트랜잭션이 되돌아가 UPDATE의 몫 증가도 취소돼야 한다.
    assert item_row(item_id).filled_slots == 1
    assert reservation_count(item_id) == 1


def test_already_joined_beats_sold_out_for_the_last_joiner(client: TestClient, setup):
    """마지막 몫을 가져간 사람이 다시 누르면 '몫 소진'이 아니라 '이미 신청함'이다."""
    item_id = setup.item(total_slots=1)
    me = setup.user()
    assert join(client, me, item_id).json()["status"] == "CONFIRMED"
    again = join(client, me, item_id)
    assert (again.status_code, again.json()["code"]) == (409, "ALREADY_JOINED")


# ---------- 실패 원인 ----------


def test_owner_cannot_join_own_item(client: TestClient, setup):
    item_id = setup.item(total_slots=3)
    res = join(client, setup.owner, item_id)
    assert (res.status_code, res.json()["code"]) == (403, "OWN_ITEM")
    assert item_row(item_id).filled_slots == 0 and reservation_count(item_id) == 0


def test_owner_on_confirmed_item_is_still_own_item(client: TestClient, setup):
    item_id = setup.item(total_slots=1, status="CONFIRMED", filled_slots=1)
    assert join(client, setup.owner, item_id).json()["code"] == "OWN_ITEM"


@pytest.mark.parametrize("bad_id", [2**62, 0, -1, 2**63])
def test_missing_item_is_404(client: TestClient, setup, bad_id):
    res = join(client, setup.user(), bad_id)
    assert (res.status_code, res.json()["code"]) == (404, "NOT_FOUND")


def test_non_numeric_item_id_is_400(client: TestClient, setup):
    res = client.post("/items/abc/join", headers=setup.user().headers)
    assert res.status_code == 400
    assert res.json()["code"] == "INVALID_INPUT" and res.json()["field"] == "item_id"


@pytest.mark.parametrize(
    "fields",
    [
        {"status": "CANCELED"},
        {"status": "FAILED"},
        {"deadline": now() - timedelta(minutes=1)},  # 저장값은 OPEN인데 마감이 지남
        {
            "status": "CONFIRMED",
            "filled_slots": 3,
            "deadline": now() - timedelta(minutes=1),
        },
    ],
    ids=["canceled", "failed", "open_but_past_deadline", "confirmed_but_past_deadline"],
)
def test_ended_items_are_410(client: TestClient, setup, fields):
    item_id = setup.item(total_slots=3, **fields)
    before = item_row(item_id)
    res = join(client, setup.user(), item_id)
    assert (res.status_code, res.json()["code"]) == (410, "EXPIRED")
    after = item_row(item_id)
    assert (after.filled_slots, after.status) == (
        before.filled_slots,
        before.status,
    )  # 아무것도 안 바뀜
    assert reservation_count(item_id) == 0


def test_join_does_not_record_failed_status(client: TestClient, setup):
    """무산 기록은 A-06·A-08에서만 한다(기획서 5.4). 신청 경로는 마감 글을 건드리지 않는다."""
    item_id = setup.item(deadline=now() - timedelta(minutes=1))
    join(client, setup.user(), item_id)
    assert item_row(item_id).status == "OPEN"


@pytest.mark.parametrize(
    "fields",
    [
        {"status": "CONFIRMED", "filled_slots": 3},
        {"status": "OPEN", "filled_slots": 3},  # 성사로 바뀌기 직전의 틈
    ],
    ids=["confirmed", "open_but_full"],
)
def test_full_items_are_409_sold_out(client: TestClient, setup, fields):
    item_id = setup.item(total_slots=3, **fields)
    res = join(client, setup.user(), item_id)
    assert (res.status_code, res.json()["code"]) == (409, "SLOTS_FULL")
    assert item_row(item_id).filled_slots == 3


def test_already_joined_is_reported_even_if_item_has_ended(client: TestClient, setup):
    """판정 순서: 이미 신청함이 마감·취소보다 앞이다(기획서 9.5)."""
    item_id = setup.item(total_slots=3, status="CANCELED")
    me = setup.user()
    insert_reservation(item_id, me.id)
    assert join(client, me, item_id).json()["code"] == "ALREADY_JOINED"


def test_join_requires_login(client: TestClient, setup):
    res = client.post(f"/items/{setup.item()}/join")
    assert (res.status_code, res.json()["code"]) == (401, "UNAUTHORIZED")


# ---------- 판정 순서 (DB 없이) ----------


def cause(**kw) -> Cause:
    base = dict(owner_id=1, status="OPEN", past_deadline=False, joined=False)
    return Cause(**{**base, **kw})


@pytest.mark.parametrize(
    "c, expected",
    [
        (None, "NOT_FOUND"),
        (cause(joined=True), "ALREADY_JOINED"),
        (
            cause(joined=True, owner_id=7, status="CANCELED", past_deadline=True),
            "ALREADY_JOINED",
        ),
        (cause(owner_id=7), "OWN_ITEM"),
        (cause(owner_id=7, status="CONFIRMED"), "OWN_ITEM"),
        (cause(owner_id=7, status="CANCELED"), "OWN_ITEM"),
        (cause(status="FAILED"), "EXPIRED"),
        (cause(status="CANCELED"), "EXPIRED"),
        (cause(past_deadline=True), "EXPIRED"),
        (cause(status="CONFIRMED", past_deadline=True), "EXPIRED"),
        (cause(status="CONFIRMED"), "SLOTS_FULL"),
        (cause(), "SLOTS_FULL"),
    ],
)
def test_failure_order(c, expected):
    # 호출하는 사용자의 id는 7이다.
    assert classify_failure(c, user_id=7) == expected
