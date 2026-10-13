"""이메일 소유 확인 (기획서 5.10, A-11, A-12). 토큰 해시 저장, 일회용, 재발송 제한, 미인증 권한 규칙."""

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import email_verification
from app.config import Settings, check_runtime
from app.db import engine
from app.email_verification import hash_token
from app.main import app
from app.suspension import AdminError, suspend_user, verify_email

from .conftest import make_user, new_email
from .helpers import insert_item, insert_user, unique_location


@pytest.fixture
def outbox(monkeypatch):
    """보낸 메일을 모은다. 링크에서 토큰 원문을 꺼내는 데 쓴다."""
    sent = []
    monkeypatch.setattr(email_verification, "send_mail", lambda to, subject, body: sent.append((to, subject, body)))
    return sent


def token_from(mail) -> str:
    return mail[2].split("/verify?token=")[1].split()[0]


def signup(client, **kw):
    email = new_email()
    res = client.post(
        "/auth/signup",
        json={"email": email, "password": "password1234", "nickname": "인증테스트", "lat": 37.5563, "lng": 126.9019, **kw},
    )
    assert res.status_code == 201, res.text
    return res.json()["id"], email


def rows(user_id):
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT * FROM email_verification_tokens WHERE user_id = :u ORDER BY id"), {"u": user_id}
        ).all()


def verified_at(user_id):
    with engine.connect() as conn:
        return conn.execute(text("SELECT email_verified_at FROM users WHERE id = :u"), {"u": user_id}).scalar_one()


def sql(stmt, **params):
    with engine.begin() as conn:
        conn.execute(text(stmt), params)


def backdate(user_id, seconds=120):
    """재발송 간격 검사를 통과하도록 토큰 발급 시각을 과거로 돌린다."""
    sql("UPDATE email_verification_tokens SET created_at = created_at - make_interval(secs => :s) WHERE user_id = :u", s=seconds, u=user_id)


def verify(client, token):
    return client.post("/auth/verify-email", json={"token": token})


def code(res):
    return res.json()["code"]


# ---------- 가입과 토큰 ----------


def test_signup_sends_mail_and_stores_only_hash(client: TestClient, outbox):
    uid, email = signup(client)
    assert verified_at(uid) is None
    [mail] = outbox
    assert mail[0] == email
    token = token_from(mail)
    [row] = rows(uid)
    assert row.token_hash == hash_token(token) and len(row.token_hash) == 64
    assert token not in str(tuple(row))  # 원문은 어디에도 저장되지 않는다
    assert row.used_at is None and row.expires_at > row.created_at


def test_signup_succeeds_even_if_mail_fails(client: TestClient, monkeypatch):
    def boom(*a):
        raise RuntimeError("smtp down")

    monkeypatch.setattr(email_verification, "send_mail", boom)
    uid, _ = signup(client)  # 가입은 성공한다
    assert verified_at(uid) is None


def test_login_reports_verification_state(client: TestClient):
    u = make_user(client, verified=False)
    assert client.post("/auth/login", json={"email": u.email, "password": "password1234"}).json()["user"]["email_verified"] is False
    sql("UPDATE users SET email_verified_at = now() WHERE id = :i", i=u.id)
    assert client.post("/auth/login", json={"email": u.email, "password": "password1234"}).json()["user"]["email_verified"] is True


# ---------- 확인 (A-11) ----------


def test_verify_marks_user_and_token_is_single_use(client: TestClient, outbox):
    uid, _ = signup(client)
    token = token_from(outbox[0])
    res = verify(client, token)
    assert (res.status_code, res.json()) == (200, {"email_verified": True})
    assert verified_at(uid) is not None and rows(uid)[0].used_at is not None
    again = verify(client, token)
    assert (again.status_code, code(again)) == (400, "INVALID_TOKEN")


@pytest.mark.parametrize("bad", ["", "nope", "x" * 201, "a" * 43])
def test_wrong_tokens_are_invalid(client: TestClient, bad):
    res = verify(client, bad)
    assert (res.status_code, code(res)) == (400, "INVALID_TOKEN")


def test_missing_token_field_is_invalid_input(client: TestClient):
    assert client.post("/auth/verify-email", json={}).status_code == 400


def test_expired_token_is_invalid(client: TestClient, outbox):
    uid, _ = signup(client)
    sql("UPDATE email_verification_tokens SET expires_at = now() - interval '1 second' WHERE user_id = :u", u=uid)
    assert code(verify(client, token_from(outbox[0]))) == "INVALID_TOKEN"
    assert verified_at(uid) is None


def test_get_does_not_consume_token(client: TestClient, outbox):
    uid, _ = signup(client)
    token = token_from(outbox[0])
    assert client.get(f"/auth/verify-email?token={token}").status_code == 405
    assert rows(uid)[0].used_at is None
    assert verify(client, token).status_code == 200


def test_valid_token_for_already_verified_account_is_idempotent(client: TestClient, outbox):
    uid, _ = signup(client)
    token = token_from(outbox[0])
    sql("UPDATE users SET email_verified_at = now() - interval '1 day' WHERE id = :i", i=uid)
    before = verified_at(uid)
    assert verify(client, token).status_code == 200
    assert verified_at(uid) == before  # 시각을 바꾸지 않는다


def test_concurrent_use_of_one_link_succeeds_once(client: TestClient, outbox):
    uid, _ = signup(client)
    token = token_from(outbox[0])
    barrier = threading.Barrier(8)

    def go(_):
        c = TestClient(app)
        barrier.wait()
        return verify(c, token).status_code

    with ThreadPoolExecutor(8) as ex:
        codes = sorted(ex.map(go, range(8)))
    assert codes == [200] + [400] * 7


# ---------- 재발송 (A-12) ----------


def test_resend_requires_login(client: TestClient):
    assert client.post("/auth/resend-verification").status_code == 401


def test_resend_too_soon_after_signup(client: TestClient, outbox):
    u = insert_user(unique_location(), "재발송", verified=False)  # 토큰이 아직 없는 미인증 계정
    assert client.post("/auth/resend-verification", headers=u.headers).status_code == 200
    res = client.post("/auth/resend-verification", headers=u.headers)  # 60초 안의 재요청
    assert (res.status_code, code(res)) == (429, "TOO_MANY_REQUESTS")
    assert len(rows(u.id)) == 1


def test_resend_invalidates_old_token_and_does_not_leak_link(client: TestClient, outbox):
    uid, email = signup(client)
    old = token_from(outbox[0])
    backdate(uid)
    token = client.post("/auth/login", json={"email": email, "password": "password1234"}).json()["access_token"]
    res = client.post("/auth/resend-verification", headers={"Authorization": f"Bearer {token}"})
    assert (res.status_code, res.json()) == (200, {"sent": True})  # 링크는 응답에 없다
    assert code(verify(client, old)) == "INVALID_TOKEN"  # 이전 토큰은 무효
    assert verify(client, token_from(outbox[1])).status_code == 200
    assert len(rows(uid)) == 2


def test_resend_limit_per_day(client: TestClient, outbox):
    u = insert_user(unique_location(), "일일제한", verified=False)
    for _ in range(5):
        with Session(engine) as db:
            email_verification.resend(db, u.id)
        backdate(u.id)
    res = client.post("/auth/resend-verification", headers=u.headers)
    assert (res.status_code, code(res)) == (429, "TOO_MANY_REQUESTS")
    assert len(rows(u.id)) == 5


def test_resend_for_verified_account_sends_nothing(client: TestClient, outbox):
    u = insert_user(unique_location(), "이미인증")
    res = client.post("/auth/resend-verification", headers=u.headers)
    assert (res.status_code, res.json()) == (200, {"sent": False})
    assert outbox == [] and rows(u.id) == []


@pytest.mark.parametrize("round_", range(5))  # 경쟁은 운에 따라 일어나므로 반복한다
def test_concurrent_resends_send_once(client: TestClient, outbox, round_):
    u = insert_user(unique_location(), "동시재발송", verified=False)
    n = 10
    barrier = threading.Barrier(n)

    def go(_):
        c = TestClient(app)
        barrier.wait()
        return c.post("/auth/resend-verification", headers=u.headers).status_code

    with ThreadPoolExecutor(n) as ex:
        codes = sorted(ex.map(go, range(n)))
    assert codes == [200] + [429] * (n - 1)
    assert len(rows(u.id)) == 1 and len(outbox) == 1


# ---------- 미인증 권한 ----------

# 인증이 필요한 모든 API는 여기에 분류돼 있어야 한다. 새 라우트를 추가하면 이 테스트가 실패해 어느 쪽인지 정하게 한다.
NEEDS_VERIFIED = {("POST", "/items"), ("POST", "/items/{item_id}/join")}
ALLOWED_UNVERIFIED = {
    ("GET", "/items"),
    ("POST", "/items/{item_id}/cancel"),
    ("GET", "/me/reservations"),
    ("GET", "/me/items"),
    ("POST", "/reports"),
    ("POST", "/auth/resend-verification"),
}


def _authenticated_operations():
    return {
        (m.upper(), path)
        for path, methods in app.openapi()["paths"].items()
        for m, op in methods.items()
        if op.get("security")
    }


def test_every_authenticated_route_is_classified():
    ops = _authenticated_operations()
    assert ops == NEEDS_VERIFIED | ALLOWED_UNVERIFIED, (
        "분류되지 않은 인증 라우트가 있습니다. 미인증 계정에 허용할지 정하세요: "
        f"{ops ^ (NEEDS_VERIFIED | ALLOWED_UNVERIFIED)}"
    )


def test_unverified_cannot_create_or_join_but_can_do_the_rest(client: TestClient):
    loc = unique_location()
    owner = insert_user(loc, "개설자")  # 인증된 개설자
    open_item = insert_item(owner.id, loc)
    me = insert_user(loc, "미인증", verified=False)

    body = {"type": "GROUP_BUY", "title": "새 글", "total_slots": 2, "total_price": 10000, "deadline": "2099-01-01T00:00:00+09:00", "pickup_note": "메모", "lat": loc[0], "lng": loc[1]}
    for method, path, kw in (
        ("POST", "/items", {"json": body}),
        ("POST", f"/items/{open_item}/join", {}),
    ):
        res = client.request(method, path, headers=me.headers, **kw)
        assert (res.status_code, code(res)) == (403, "EMAIL_NOT_VERIFIED"), path

    assert client.get("/items", params={"type": "GROUP_BUY", "lat": loc[0], "lng": loc[1]}, headers=me.headers).status_code == 200
    assert client.get("/me/reservations", headers=me.headers).status_code == 200
    assert client.get("/me/items", headers=me.headers).status_code == 200
    r = client.post("/reports", json={"item_id": open_item, "reason": "FRAUD"}, headers=me.headers)
    assert r.status_code == 201, r.text
    mine = insert_item(me.id, loc)  # 진행 중인 거래(예: 인증 전에 올린 글)는 취소할 수 있다
    assert client.post(f"/items/{mine}/cancel", headers=me.headers).status_code == 200


def test_verified_user_can_create_and_join(client: TestClient):
    loc = unique_location()
    owner, joiner = insert_user(loc, "개설자"), insert_user(loc, "참여자")
    item = insert_item(owner.id, loc)
    assert client.post(f"/items/{item}/join", headers=joiner.headers).status_code == 201


def test_unverified_flow_end_to_end(client: TestClient, outbox):
    """가입 → 신청 거절 → 링크 확인 → 같은 토큰으로 신청 성공."""
    loc = unique_location()
    owner = insert_user(loc, "개설자")
    item = insert_item(owner.id, loc)
    uid, email = signup(client, lat=loc[0], lng=loc[1])
    jwt = client.post("/auth/login", json={"email": email, "password": "password1234"}).json()["access_token"]
    h = {"Authorization": f"Bearer {jwt}"}
    assert code(client.post(f"/items/{item}/join", headers=h)) == "EMAIL_NOT_VERIFIED"
    assert verify(client, token_from(outbox[0])).status_code == 200
    assert client.post(f"/items/{item}/join", headers=h).status_code == 201


def test_suspension_is_checked_before_verification(client: TestClient):
    me = insert_user(unique_location(), "둘다", verified=False)
    with Session(engine) as db:
        suspend_user(db, me.id, "테스트", "pytest")
    res = client.post("/items/1/join", headers=me.headers)
    assert code(res) == "ACCOUNT_SUSPENDED"


# ---------- 운영자 인증, 설정, 발송 ----------


def test_admin_verify_email_is_recorded():
    u = insert_user(unique_location(), "운영인증", verified=False)
    with Session(engine) as db:
        verify_email(db, u.id, "시연 계정", "pytest")
    assert verified_at(u.id) is not None
    with engine.connect() as conn:
        acts = conn.execute(text("SELECT action, actor_os_user FROM admin_actions WHERE target_user_id = :u"), {"u": u.id}).all()
    assert [tuple(a) for a in acts] == [("VERIFY_EMAIL", "pytest")]
    with Session(engine) as db, pytest.raises(AdminError):
        verify_email(db, u.id, "again", "pytest")


def settings(**kw):
    return Settings(database_url="postgresql://x:y@h/db", jwt_secret="s", _env_file=None, **kw)


def test_production_refuses_console_mail():
    with pytest.raises(RuntimeError, match="console"):
        check_runtime(settings(app_env="production", mail_backend="console"))


def test_other_unsafe_mail_configs_are_refused():
    with pytest.raises(RuntimeError):
        check_runtime(settings(mail_backend="carrier-pigeon"))
    with pytest.raises(RuntimeError):
        check_runtime(settings(app_env="production", mail_backend="smtp"))  # 호스트·발신자 없음


def test_valid_mail_configs_start():
    check_runtime(settings())  # 개발 기본값: console
    check_runtime(settings(app_env="production", mail_backend="smtp", smtp_host="smtp.example.com", mail_from="no-reply@example.com"))


def test_console_backend_prints_instead_of_sending(capsys):
    from app.mail import send_mail

    send_mail("a@example.com", "제목", "본문 링크")
    out = capsys.readouterr().out
    assert "a@example.com" in out and "본문 링크" in out


def test_token_table_constraints():
    uid = insert_user(unique_location(), "제약", verified=False).id
    ins = "INSERT INTO email_verification_tokens (user_id, token_hash, expires_at) VALUES (:u, :h, now())"
    with pytest.raises(IntegrityError):
        sql(ins, u=uid, h="short")  # 해시는 64자
    sql(ins, u=uid, h="a" * 64)
    with pytest.raises(IntegrityError):
        sql(ins, u=uid, h="a" * 64)  # 해시는 유일
