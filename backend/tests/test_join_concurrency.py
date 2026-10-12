"""A-05 동시 신청. 이 서비스의 핵심 약속을 검사한다(기획서 TS-01, TS-02).

여러 요청을 장벽(Barrier)으로 같은 순간에 출발시키고, 누가 이기든 항상 지켜져야 하는 규칙만 검사한다.
- 성공한 요청 수 = 남은 몫 수
- filled_slots = 신청 기록 수 (어긋나면 안 된다)
- 5xx(교착 등) 없음
"""

import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app.main import app

from .helpers import (
    insert_item,
    insert_user,
    item_row,
    reservation_count,
    unique_location,
)

ROUNDS = 5  # 경쟁은 운에 따라 일어나므로 여러 번 반복한다


def fire(jobs: list[tuple]) -> list[tuple[int, str | None]]:
    """jobs = [(사용자, 글 id), ...]를 같은 순간에 보내고 (HTTP 상태, 에러 코드) 목록을 돌려준다."""
    barrier = threading.Barrier(len(jobs))

    def one(job):
        user, item_id = job
        client = TestClient(app)  # 스레드마다 따로 쓴다
        barrier.wait()
        res = client.post(f"/items/{item_id}/join", headers=user.headers)
        return res.status_code, (
            res.json().get("code") if res.status_code != 201 else None
        )

    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        return list(pool.map(one, jobs))


def assert_consistent(
    item_id: int, results: list[tuple[int, str | None]], expect_success: int
):
    codes = Counter(code for _, code in results)
    statuses = Counter(status for status, _ in results)
    assert not any(s >= 500 for s in statuses), f"서버 오류가 났습니다: {results}"
    assert statuses[201] == expect_success, (
        f"성공 {statuses[201]}건, 기대 {expect_success}건: {results}"
    )

    row = item_row(item_id)
    # 핵심 불변식: 몫 수와 신청 기록 수가 항상 같다
    assert row.filled_slots == reservation_count(item_id) == expect_success
    assert row.filled_slots <= row.total_slots
    return codes, row


@pytest.mark.parametrize("round_no", range(ROUNDS))
def test_last_slot_goes_to_exactly_one_of_many(round_no):
    """마지막 한 몫에 8명이 동시에 신청하면 정확히 1명만 성공한다."""
    loc = unique_location()
    owner = insert_user(loc, "개설자")
    item_id = insert_item(owner.id, loc, total_slots=1)
    users = [insert_user(loc, f"참여자{i}") for i in range(8)]

    results = fire([(u, item_id) for u in users])
    codes, row = assert_consistent(item_id, results, expect_success=1)

    assert codes["SLOTS_FULL"] == 7 and set(codes) == {None, "SLOTS_FULL"}
    assert row.status == "CONFIRMED"  # 마지막 몫이 찼으니 성사


@pytest.mark.parametrize("round_no", range(ROUNDS))
def test_remaining_slots_are_never_oversold(round_no):
    """몫 3개에 8명이 동시에 신청하면 정확히 3명만 성공한다."""
    loc = unique_location()
    owner = insert_user(loc, "개설자")
    item_id = insert_item(owner.id, loc, total_slots=3)
    users = [insert_user(loc, f"참여자{i}") for i in range(8)]

    results = fire([(u, item_id) for u in users])
    codes, row = assert_consistent(item_id, results, expect_success=3)

    assert codes["SLOTS_FULL"] == 5 and set(codes) == {None, "SLOTS_FULL"}
    assert (row.filled_slots, row.status) == (3, "CONFIRMED")


@pytest.mark.parametrize("round_no", range(ROUNDS))
def test_same_user_twice_on_last_slot_gets_already_joined(round_no):
    """같은 계정이 마지막 몫에 동시에 두 번: 1건 성공, 나머지는 '이미 신청함'이다(몫 소진 아님)."""
    loc = unique_location()
    owner = insert_user(loc, "개설자")
    item_id = insert_item(owner.id, loc, total_slots=1)
    me = insert_user(loc)

    results = fire([(me, item_id)] * 2)
    codes, row = assert_consistent(item_id, results, expect_success=1)

    assert codes["ALREADY_JOINED"] == 1 and set(codes) == {None, "ALREADY_JOINED"}, (
        results
    )
    assert row.status == "CONFIRMED"


@pytest.mark.parametrize("round_no", range(ROUNDS))
def test_same_user_twice_with_slots_left_is_rolled_back(round_no):
    """몫이 남아 있을 때 같은 계정이 동시에 두 번: 둘 다 UPDATE는 성공하지만
    늦은 쪽이 UNIQUE 위반으로 롤백되어 몫이 두 번 늘면 안 된다."""
    loc = unique_location()
    owner = insert_user(loc, "개설자")
    item_id = insert_item(owner.id, loc, total_slots=3)
    me = insert_user(loc)

    results = fire([(me, item_id)] * 3)
    codes, row = assert_consistent(item_id, results, expect_success=1)

    assert codes["ALREADY_JOINED"] == 2 and set(codes) == {None, "ALREADY_JOINED"}, (
        results
    )
    assert (row.filled_slots, row.status) == (1, "OPEN")  # 롤백으로 증가가 취소됐다


@pytest.mark.parametrize("round_no", range(ROUNDS))
def test_mixed_duplicates_and_competition(round_no):
    """두 사람이 각각 두 번씩 동시에 마지막 몫에: 이긴 사람의 중복은 '이미 신청함', 진 사람은 '몫 소진'."""
    loc = unique_location()
    owner = insert_user(loc, "개설자")
    item_id = insert_item(owner.id, loc, total_slots=1)
    a, b = insert_user(loc, "A"), insert_user(loc, "B")

    results = fire([(a, item_id), (a, item_id), (b, item_id), (b, item_id)])
    codes, _ = assert_consistent(item_id, results, expect_success=1)

    by_user = {"A": results[0:2], "B": results[2:4]}
    winner = "A" if any(s == 201 for s, _ in by_user["A"]) else "B"
    loser = "B" if winner == "A" else "A"
    assert sorted(c or "OK" for _, c in by_user[winner]) == ["ALREADY_JOINED", "OK"], (
        results
    )
    assert [c for _, c in by_user[loser]] == ["SLOTS_FULL", "SLOTS_FULL"], results


def test_owner_joining_during_competition_never_gets_a_slot():
    loc = unique_location()
    owner = insert_user(loc, "개설자")
    item_id = insert_item(owner.id, loc, total_slots=2)
    users = [insert_user(loc, f"참여자{i}") for i in range(3)]

    results = fire([(owner, item_id)] + [(u, item_id) for u in users])
    assert_consistent(item_id, results, expect_success=2)
    assert results[0] == (403, "OWN_ITEM")
