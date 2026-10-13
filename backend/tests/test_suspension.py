"""계정 정지 (기획서 5.9, F-15). 정지된 계정의 차단, 글 처리, 표시, 운영 기록, 정지와 신청의 경쟁."""

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import engine
from app.main import app
from app.suspension import AdminError, resolve_report, suspend_user, unsuspend_user

from .conftest import make_user
from .helpers import (
    insert_item,
    insert_reservation,
    insert_user,
    item_row,
    reservation_count,
    unique_location,
)


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


def ban(user_id, reason="테스트 정지"):
    with Session(engine) as db:
        return suspend_user(db, user_id, reason, "pytest")


def unban(user_id):
    with Session(engine) as db:
        unsuspend_user(db, user_id, "테스트 해제", "pytest")


def user_row(user_id):
    with engine.connect() as conn:
        return conn.execute(text("SELECT * FROM users WHERE id = :i"), {"i": user_id}).one()


def actions(user_id):
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT action, actor_os_user, note, report_id FROM admin_actions WHERE target_user_id = :i ORDER BY id"),
            {"i": user_id},
        ).all()


# ---------- 로그인과 토큰 ----------


def test_login_reveals_suspension_only_with_right_password(client: TestClient):
    u = make_user(client)
    ban(u.id)
    ok = client.post("/auth/login", json={"email": u.email, "password": "password1234"})
    assert (ok.status_code, ok.json()["code"]) == (403, "ACCOUNT_SUSPENDED")
    bad = client.post("/auth/login", json={"email": u.email, "password": "wrong-password"})
    assert (bad.status_code, bad.json()["code"]) == (401, "INVALID_CREDENTIALS")
    unban(u.id)
    assert client.post("/auth/login", json={"email": u.email, "password": "password1234"}).status_code == 200


def test_token_issued_before_suspension_is_blocked_immediately(client: TestClient, town):
    u = town.user()
    assert client.get("/me/items", headers=u.headers).status_code == 200
    ban(u.id)
    res = client.get("/me/items", headers=u.headers)
    assert (res.status_code, res.json()["code"]) == (403, "ACCOUNT_SUSPENDED")
    unban(u.id)  # 해제하면 같은 토큰이 다시 통한다
    assert client.get("/me/items", headers=u.headers).status_code == 200


def _authenticated_operations() -> list[tuple[str, str]]:
    """OpenAPI에서 Bearer 인증이 붙은 (메서드, 경로) 전부. 라우터 구조가 바뀌어도 새 라우트를 놓치지 않는다.

    shortcut: Bearer 인증 표시로 찾는다. get_current_user를 쓰지 않고 토큰을 직접 해석하는 라우트는 못 찾는다.
    """
    ops = []
    for path, methods in app.openapi()["paths"].items():
        for method, op in methods.items():
            if op.get("security"):
                ops.append((method.upper(), path))
    return ops


def test_every_authenticated_route_blocks_suspended_users(client: TestClient, town):
    """새 라우트가 생겨도 정지 검사를 우회하지 못한다: 인증이 필요한 라우트를 전부 훑어 확인한다."""
    u = town.user()
    ban(u.id)
    ops = _authenticated_operations()
    assert len(ops) >= 7, f"인증 필요 라우트를 못 찾았습니다(검사가 헛돌고 있을 수 있음): {ops}"
    for method, route_path in ops:
        path = route_path.replace("{item_id}", "1")
        assert "{" not in path, f"경로 변수를 채우지 못했습니다: {route_path}"
        res = client.request(method, path, headers=u.headers, json={} if method != "GET" else None)
        assert res.status_code == 403 and res.json()["code"] == "ACCOUNT_SUSPENDED", (
            method, route_path, res.status_code, res.text
        )


def test_no_user_facing_route_can_lift_a_suspension():
    paths = list(app.openapi()["paths"])
    assert not [p for p in paths if "suspend" in p or "admin" in p or "ban" in p], paths


# ---------- 글과 신청 ----------


def test_suspension_cancels_open_items_but_keeps_confirmed_and_records(client: TestClient, town):
    joiner = town.user()
    open_item = town.item(total_slots=3, filled_slots=1)
    insert_reservation(open_item, joiner.id)
    confirmed = town.item(total_slots=1, filled_slots=1, status="CONFIRMED")
    insert_reservation(confirmed, joiner.id)
    failed = town.item(status="FAILED")
    mine_elsewhere = insert_item(joiner.id, unique_location())  # 다른 사람의 글은 건드리지 않는다

    canceled = ban(town.owner.id)

    assert canceled == [open_item]
    assert item_row(open_item).status == "CANCELED"
    assert item_row(confirmed).status == "CONFIRMED"
    assert item_row(failed).status == "FAILED"
    assert item_row(mine_elsewhere).status == "OPEN"
    assert reservation_count(open_item) == 1 and reservation_count(confirmed) == 1  # 기록은 지우지 않는다
    assert user_row(town.owner.id).status == "SUSPENDED"


def test_suspension_fields_and_state(town):
    ban(town.owner.id, "사유 메모")
    row = user_row(town.owner.id)
    assert (row.status, row.suspension_reason) == ("SUSPENDED", "사유 메모")
    assert row.suspended_at is not None
    with pytest.raises(AdminError):
        ban(town.owner.id)  # 이미 정지
    unban(town.owner.id)
    row = user_row(town.owner.id)
    assert (row.status, row.suspended_at, row.suspension_reason) == ("ACTIVE", None, None)
    with pytest.raises(AdminError):
        unban(town.owner.id)  # 정지 상태가 아님


def test_owner_suspended_flag_for_participants(client: TestClient, town):
    joiner = town.user()
    item = town.item(total_slots=1, filled_slots=1, status="CONFIRMED")
    insert_reservation(item, joiner.id)
    [r] = client.get("/me/reservations", headers=joiner.headers).json()["reservations"]
    assert r["item"]["owner_suspended"] is False

    ban(town.owner.id)
    [r] = client.get("/me/reservations", headers=joiner.headers).json()["reservations"]
    assert r["item"]["owner_suspended"] is True
    assert r["item"]["status"] == "CONFIRMED" and r["item"]["pickup_note"] == "메모"  # 약속된 만남은 유지
    assert "suspension" not in str(r) and "사유" not in str(r)  # 사유는 노출하지 않는다

    unban(town.owner.id)
    [r] = client.get("/me/reservations", headers=joiner.headers).json()["reservations"]
    assert r["item"]["owner_suspended"] is False


def test_user_suspended_flag_for_owner_including_open_items(client: TestClient, town):
    a, b = town.user("가"), town.user("나")
    item = town.item(total_slots=3, filled_slots=2)
    insert_reservation(item, a.id)
    insert_reservation(item, b.id)
    ban(a.id, "비공개 사유")

    [it] = client.get("/me/items", headers=town.owner.headers).json()["items"]
    assert it["status"] == "OPEN"  # 참여자 정지로 글이 바뀌지 않는다
    assert {p["nickname"]: p["user_suspended"] for p in it["participants"]} == {"가": True, "나": False}
    assert "비공개 사유" not in str(it)

    unban(a.id)
    [it] = client.get("/me/items", headers=town.owner.headers).json()["items"]
    assert not any(p["user_suspended"] for p in it["participants"])


def test_canceled_items_are_not_restored_on_unsuspend(town):
    item = town.item()
    ban(town.owner.id)
    unban(town.owner.id)
    assert item_row(item).status == "CANCELED"


# ---------- 운영 기록과 신고 처리 ----------


def test_admin_actions_are_recorded(town):
    ban(town.owner.id, "사유")
    unban(town.owner.id)
    assert [(a.action, a.actor_os_user) for a in actions(town.owner.id)] == [
        ("SUSPEND", "pytest"),
        ("UNSUSPEND", "pytest"),
    ]


def _report(town, reporter, target_item_owner_is_target=True):
    item = town.item()
    with engine.begin() as conn:
        return conn.execute(
            text(
                "INSERT INTO reports (reporter_id, target_user_id, item_id, reason) "
                "VALUES (:r, :t, :i, 'FRAUD') RETURNING id"
            ),
            {"r": reporter.id, "t": town.owner.id, "i": item},
        ).scalar_one(), item


def test_resolve_dismiss_leaves_account_alone(town):
    rid, item = _report(town, town.user())
    with Session(engine) as db:
        assert resolve_report(db, rid, "DISMISSED", "근거 없음", "pytest") == []
    assert user_row(town.owner.id).status == "ACTIVE" and item_row(item).status == "OPEN"
    with engine.connect() as conn:
        r = conn.execute(text("SELECT status, resolution, resolved_at, resolution_note FROM reports WHERE id=:i"), {"i": rid}).one()
    assert (r.status, r.resolution, r.resolution_note) == ("RESOLVED", "DISMISSED", "근거 없음") and r.resolved_at
    assert [(a.action, a.report_id) for a in actions(town.owner.id)] == [("RESOLVE_REPORT", rid)]
    with Session(engine) as db, pytest.raises(AdminError):
        resolve_report(db, rid, "DISMISSED", "again", "pytest")  # 이미 처리됨


def test_resolve_suspend_suspends_target_and_cancels_open_items(town):
    rid, item = _report(town, town.user())
    with Session(engine) as db:
        assert resolve_report(db, rid, "SUSPENDED", "확인됨", "pytest") == [item]
    assert user_row(town.owner.id).status == "SUSPENDED" and item_row(item).status == "CANCELED"
    assert [a.action for a in actions(town.owner.id)] == ["SUSPEND", "RESOLVE_REPORT"]


def test_report_alone_never_suspends(client: TestClient, town):
    reporter = town.user()
    item = town.item()
    assert client.post("/reports", json={"item_id": item, "reason": "FRAUD"}, headers=reporter.headers).status_code == 201
    assert user_row(town.owner.id).status == "ACTIVE"
    assert client.get("/me/items", headers=town.owner.headers).status_code == 200


# ---------- DB 제약 ----------


def test_db_constraints_on_suspension_columns(town):
    for sql in (
        "UPDATE users SET status = 'SUSPENDED' WHERE id = :i",  # 정지인데 시각 없음
        "UPDATE users SET suspended_at = now() WHERE id = :i",  # 시각만 있음
        "UPDATE users SET status = 'BANNED', suspended_at = now() WHERE id = :i",
    ):
        with pytest.raises(IntegrityError), engine.begin() as conn:
            conn.execute(text(sql), {"i": town.owner.id})
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(
            text("INSERT INTO admin_actions (action, target_user_id, actor_os_user) VALUES ('DELETE', :i, 'x')"),
            {"i": town.owner.id},
        )


# ---------- 정지와 마지막 신청의 경쟁 (5.9 동시성) ----------


def test_suspend_first_then_last_join_is_expired(client: TestClient, town):
    joiner = town.user()
    item = town.item(total_slots=1, filled_slots=0)
    ban(town.owner.id)
    res = client.post(f"/items/{item}/join", headers=joiner.headers)
    assert (res.status_code, res.json()["code"]) == (410, "EXPIRED")
    assert item_row(item).status == "CANCELED" and reservation_count(item) == 0


def test_join_first_then_suspend_keeps_confirmed(client: TestClient, town):
    joiner = town.user()
    item = town.item(total_slots=1, filled_slots=0)
    assert client.post(f"/items/{item}/join", headers=joiner.headers).status_code == 201
    assert ban(town.owner.id) == []  # 이미 성사돼 취소할 글이 없다
    row = item_row(item)
    assert (row.status, row.filled_slots, reservation_count(item)) == ("CONFIRMED", 1, 1)


@pytest.mark.parametrize("round_", range(6))
def test_suspend_and_last_join_race_is_consistent(town, round_):
    """누가 이기든: 신청이 성공했으면 글은 CONFIRMED로 남고, 아니면 CANCELED. 몫 수와 신청 기록 수는 항상 같다."""
    joiner = town.user()
    item = town.item(total_slots=1, filled_slots=0)
    barrier = threading.Barrier(2)

    def do_join():
        c = TestClient(app)
        barrier.wait()
        return c.post(f"/items/{item}/join", headers=joiner.headers)

    def do_ban():
        barrier.wait()
        return ban(town.owner.id)

    with ThreadPoolExecutor(2) as ex:
        fj, fb = ex.submit(do_join), ex.submit(do_ban)
        join, canceled = fj.result(), fb.result()

    assert join.status_code in (201, 410), join.text
    row = item_row(item)
    assert row.filled_slots == reservation_count(item)
    if join.status_code == 201:
        assert (row.status, canceled) == ("CONFIRMED", [])
    else:
        assert (row.status, canceled, row.filled_slots) == ("CANCELED", [item], 0)
