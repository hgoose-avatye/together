"""A-09 개설 취소 (기획서 9.7). 신청(A-05)과의 동시 경쟁도 검사한다."""

import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app

from .helpers import (
    insert_item,
    insert_reservation,
    insert_user,
    item_row,
    reservation_count,
    unique_location,
)

PAST = lambda: datetime.now(timezone.utc) - timedelta(minutes=1)  # noqa: E731


@pytest.fixture
def town():
    loc = unique_location()

    class T:
        owner = insert_user(loc, "개설자")

        def user(self, nickname="참여자"):
            return insert_user(loc, nickname)

        def item(self, **kw):
            return insert_item(self.owner.id, loc, **kw)

    return T()


def cancel(client: TestClient, user, item_id):
    return client.post(f"/items/{item_id}/cancel", headers=user.headers)


# ---------- 성공 ----------


def test_owner_cancels_open_item(client: TestClient, town):
    item_id = town.item(title="내 글", total_slots=3, filled_slots=1)
    joiner = town.user("라면왕")
    insert_reservation(item_id, joiner.id)

    res = cancel(client, town.owner, item_id)
    assert res.status_code == 200, res.text
    body = res.json()
    assert (body["id"], body["status"], body["pickup_note"]) == (
        item_id,
        "CANCELED",
        "메모",
    )
    assert [p["nickname"] for p in body["participants"]] == ["라면왕"]  # A-08 항목 형식
    assert item_row(item_id).status == "CANCELED"
    assert reservation_count(item_id) == 1  # 이미 한 신청은 지우지 않는다

    # 목록에서는 사라지고, 참여자에게는 '취소'로 보이며 메모는 열리지 않는다
    listed = client.get(
        "/items", params={"type": "GROUP_BUY"}, headers=joiner.headers
    ).json()["items"]
    assert item_id not in [i["id"] for i in listed]
    [r] = client.get("/me/reservations", headers=joiner.headers).json()["reservations"]
    assert (r["item"]["status"], r["item"]["pickup_note"]) == ("CANCELED", None)


def test_joining_a_canceled_item_is_410(client: TestClient, town):
    item_id = town.item()
    cancel(client, town.owner, item_id)
    res = client.post(f"/items/{item_id}/join", headers=town.user().headers)
    assert (res.status_code, res.json()["code"]) == (410, "EXPIRED")


# ---------- 실패 ----------


def test_other_user_cannot_cancel(client: TestClient, town):
    item_id = town.item()
    res = cancel(client, town.user(), item_id)
    assert (res.status_code, res.json()["code"]) == (403, "NOT_OWNER")
    assert item_row(item_id).status == "OPEN"


@pytest.mark.parametrize(
    "fields",
    [
        {"status": "CONFIRMED", "filled_slots": 3},
        {"status": "CANCELED"},
        {"status": "FAILED"},
        {"deadline": PAST()},  # 저장값은 OPEN인데 마감이 지남
    ],
    ids=["confirmed", "already_canceled", "failed", "open_but_expired"],
)
def test_ended_items_are_409_not_open(client: TestClient, town, fields):
    item_id = town.item(total_slots=3, **fields)
    before = item_row(item_id).status
    res = cancel(client, town.owner, item_id)
    assert (res.status_code, res.json()["code"]) == (409, "NOT_OPEN")
    assert (
        item_row(item_id).status == before
    )  # 마감 지난 OPEN도 취소 경로가 FAILED로 바꾸지 않는다


def test_cancel_twice_second_is_not_open(client: TestClient, town):
    item_id = town.item()
    assert cancel(client, town.owner, item_id).status_code == 200
    assert cancel(client, town.owner, item_id).json()["code"] == "NOT_OPEN"


def test_not_owner_is_checked_before_not_open(client: TestClient, town):
    """판정 순서: 글 없음 -> 남의 글 -> 그 밖. 남의 끝난 글은 NOT_OPEN이 아니라 NOT_OWNER."""
    item_id = town.item(status="CONFIRMED", filled_slots=3)
    assert cancel(client, town.user(), item_id).json()["code"] == "NOT_OWNER"


@pytest.mark.parametrize("bad_id", [2**62, 0, -1, 2**63])
def test_missing_item_is_404(client: TestClient, town, bad_id):
    res = cancel(client, town.owner, bad_id)
    assert (res.status_code, res.json()["code"]) == (404, "NOT_FOUND")


def test_non_numeric_id_is_400_and_login_required(client: TestClient, town):
    res = client.post("/items/abc/cancel", headers=town.owner.headers)
    assert (res.status_code, res.json()["field"]) == (400, "item_id")
    res = client.post(f"/items/{town.item()}/cancel")
    assert (res.status_code, res.json()["code"]) == (401, "UNAUTHORIZED")


# ---------- 동시성 ----------


def fire(jobs: list[tuple[str, object, int]]) -> list[tuple[str, int, str | None]]:
    """jobs = [('join'|'cancel', 사용자, 글 id)]를 같은 순간에 보내고 (종류, 상태, 에러 코드)를 돌려준다."""
    barrier = threading.Barrier(len(jobs))

    def one(job):
        kind, user, item_id = job
        client = TestClient(app)
        barrier.wait()
        res = client.post(f"/items/{item_id}/{kind}", headers=user.headers)
        return (
            kind,
            res.status_code,
            (res.json().get("code") if res.status_code >= 400 else None),
        )

    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        return list(pool.map(one, jobs))


@pytest.mark.parametrize("round_no", range(5))
def test_join_and_cancel_race_has_exactly_one_winner(town, round_no):
    """마지막 한 몫에 신청과 취소가 동시에: 신청이 먼저면 성사(취소 거절), 취소가 먼저면 취소(신청 거절)."""
    item_id = town.item(total_slots=1)
    results = fire([("join", town.user(), item_id), ("cancel", town.owner, item_id)])
    by_kind = {kind: (status, code) for kind, status, code in results}
    row = item_row(item_id)

    if by_kind["join"][0] == 201:  # 신청이 이김
        assert by_kind["cancel"] == (409, "NOT_OPEN")
        assert (row.status, row.filled_slots, reservation_count(item_id)) == (
            "CONFIRMED",
            1,
            1,
        )
    else:  # 취소가 이김
        assert by_kind["cancel"][0] == 200 and by_kind["join"] == (410, "EXPIRED")
        assert (row.status, row.filled_slots, reservation_count(item_id)) == (
            "CANCELED",
            0,
            0,
        )


@pytest.mark.parametrize("round_no", range(3))
def test_double_cancel_race_has_one_winner(town, round_no):
    item_id = town.item()
    results = fire([("cancel", town.owner, item_id)] * 3)
    assert Counter(s for _, s, _ in results) == {200: 1, 409: 2}
    assert {c for _, _, c in results} == {None, "NOT_OPEN"}
    assert item_row(item_id).status == "CANCELED"
