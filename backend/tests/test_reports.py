"""A-10 신고 (기획서 5.9). 접수만 하고 자동 제재는 하지 않는다."""

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db import engine
from app.main import app

from .helpers import insert_item, insert_reservation, insert_user, unique_location


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


def report(client, user, **body):
    return client.post("/reports", json=body, headers=user.headers)


def rows(item_id):
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT * FROM reports WHERE item_id = :i ORDER BY id"), {"i": item_id}
        ).all()


def code(res):
    return res.json()["code"]


# ---------- 성공 ----------


def test_report_owner(client: TestClient, town):
    item_id = town.item()
    me = town.user()
    res = report(client, me, item_id=item_id, reason="FRAUD", detail="  돈을 먼저 달라고 함  ")
    assert res.status_code == 201, res.text
    assert res.json()["status"] == "OPEN" and isinstance(res.json()["id"], int)
    [r] = rows(item_id)
    assert (r.reporter_id, r.target_user_id, r.reason, r.detail, r.status) == (
        me.id, town.owner.id, "FRAUD", "돈을 먼저 달라고 함", "OPEN",
    )


def test_owner_reports_participant(client: TestClient, town):
    item_id = town.item()
    joiner = town.user()
    rid = insert_reservation(item_id, joiner.id)
    res = report(client, town.owner, item_id=item_id, reservation_id=rid, reason="THREAT")
    assert res.status_code == 201, res.text
    [r] = rows(item_id)
    assert (r.reporter_id, r.target_user_id, r.detail) == (town.owner.id, joiner.id, "")


def test_reporting_does_not_sanction(client: TestClient, town):
    """신고가 쌓여도 대상은 그대로 쓸 수 있고 글도 그대로다(자동 제재 없음)."""
    item_id = town.item()
    for i in range(3):
        assert report(client, town.user(f"신고자{i}"), item_id=item_id, reason="INAPPROPRIATE").status_code == 201
    assert client.get("/me/items", headers=town.owner.headers).status_code == 200
    [item] = client.get("/me/items", headers=town.owner.headers).json()["items"]
    assert item["status"] == "OPEN"


# ---------- 실패 ----------


def test_requires_login(client: TestClient, town):
    res = client.post("/reports", json={"item_id": town.item(), "reason": "FRAUD"})
    assert res.status_code == 401


def test_self_report_rejected(client: TestClient, town):
    res = report(client, town.owner, item_id=town.item(), reason="FRAUD")
    assert (res.status_code, code(res)) == (400, "INVALID_INPUT")
    assert res.json()["field"] == "item_id"


@pytest.mark.parametrize("item_id", [0, -1, 2**63, 10**18])
def test_unknown_item(client: TestClient, town, item_id):
    res = report(client, town.user(), item_id=item_id, reason="FRAUD")
    assert (res.status_code, code(res)) == (404, "NOT_FOUND")


@pytest.mark.parametrize(
    "body",
    [
        {"reason": "NOPE"},
        {"reason": "OTHER"},
        {"reason": "OTHER", "detail": "   "},
        {"reason": "FRAUD", "detail": "가" * 501},
    ],
)
def test_invalid_input(client: TestClient, town, body):
    res = report(client, town.user(), item_id=town.item(), **body)
    assert (res.status_code, code(res)) == (400, "INVALID_INPUT")
    assert not res.json()["message"].startswith("Value error")


def test_other_with_detail_ok_and_max_length(client: TestClient, town):
    item_id = town.item()
    assert report(client, town.user(), item_id=item_id, reason="OTHER", detail="x").status_code == 201
    assert report(client, town.user(), item_id=item_id, reason="FRAUD", detail="가" * 500).status_code == 201


def test_duplicate_report(client: TestClient, town):
    item_id = town.item()
    me = town.user()
    assert report(client, me, item_id=item_id, reason="FRAUD").status_code == 201
    res = report(client, me, item_id=item_id, reason="THREAT")  # 사유가 달라도 같은 대상·글
    assert (res.status_code, code(res)) == (409, "ALREADY_REPORTED")
    assert len(rows(item_id)) == 1


def test_same_target_other_item_is_separate(client: TestClient, town):
    me = town.user()
    a, b = town.item(), town.item()
    assert report(client, me, item_id=a, reason="FRAUD").status_code == 201
    assert report(client, me, item_id=b, reason="FRAUD").status_code == 201


def test_non_owner_cannot_report_participant(client: TestClient, town):
    item_id = town.item()
    joiner = town.user()
    rid = insert_reservation(item_id, joiner.id)
    stranger = town.user("남")
    res = report(client, stranger, item_id=item_id, reservation_id=rid, reason="FRAUD")
    assert (res.status_code, code(res)) == (403, "NOT_OWNER")
    # 존재하지 않는 신청 id여도 같은 응답이어야 신청 기록의 존재를 알아낼 수 없다
    res = report(client, stranger, item_id=item_id, reservation_id=rid + 10**6, reason="FRAUD")
    assert (res.status_code, code(res)) == (403, "NOT_OWNER")
    assert rows(item_id) == []


def test_reservation_must_belong_to_item(client: TestClient, town):
    item_id, other_id = town.item(), town.item()
    joiner = town.user()
    rid = insert_reservation(other_id, joiner.id)
    res = report(client, town.owner, item_id=item_id, reservation_id=rid, reason="FRAUD")
    assert (res.status_code, code(res)) == (404, "NOT_FOUND")
    for bad in (0, 2**63):
        res = report(client, town.owner, item_id=item_id, reservation_id=bad, reason="FRAUD")
        assert (res.status_code, code(res)) == (404, "NOT_FOUND")


def test_client_cannot_choose_target(client: TestClient, town):
    """target_user_id를 보내도 무시되고, 대상은 서버가 정한다."""
    item_id = town.item()
    me, victim = town.user(), town.user("피해자")
    res = report(client, me, item_id=item_id, reason="FRAUD", target_user_id=victim.id)
    assert res.status_code == 201
    assert rows(item_id)[0].target_user_id == town.owner.id


# ---------- 동시성 / DB 제약 ----------


def test_concurrent_double_submit_creates_one(client: TestClient, town):
    item_id = town.item()
    me = town.user()
    barrier = threading.Barrier(8)

    def go(_):
        with TestClient(app) as c:
            barrier.wait()
            return report(c, me, item_id=item_id, reason="FRAUD").status_code

    with ThreadPoolExecutor(8) as ex:
        codes = list(ex.map(go, range(8)))
    assert sorted(codes) == [201] + [409] * 7
    assert len(rows(item_id)) == 1


def _insert_report(**kw):
    vals = {"detail": "", "status": "OPEN", "resolution": None, "resolved_at": None, **kw}
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO reports (reporter_id, target_user_id, item_id, reason, detail, status, resolution, resolved_at) "
                "VALUES (:reporter_id, :target_user_id, :item_id, :reason, :detail, :status, :resolution, "
                "CAST(:resolved_at AS timestamptz))"
            ),
            vals,
        )


def test_db_constraints(town):
    item_id = town.item()
    a, b = town.user("a"), town.user("b")
    base = dict(reporter_id=a.id, target_user_id=b.id, item_id=item_id, reason="FRAUD")
    for bad in (
        {"target_user_id": a.id},  # 자기 신고
        {"reason": "NOPE"},
        {"reason": "OTHER", "detail": "  "},
        {"status": "RESOLVED"},  # 처리 결과 없이 처리됨
        {"resolution": "DISMISSED"},  # 열려 있는데 결과가 있음
        {"status": "RESOLVED", "resolution": "BAN", "resolved_at": "2026-01-01"},
    ):
        with pytest.raises(IntegrityError):
            _insert_report(**{**base, **bad})
    _insert_report(**base)
    with pytest.raises(IntegrityError):  # 중복
        _insert_report(**base)
    _insert_report(**{**base, "reporter_id": b.id, "target_user_id": a.id})  # 반대 방향은 별개
