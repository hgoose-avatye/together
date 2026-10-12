"""A-01 회원가입, A-02 로그인, 인증 의존성. 개발용 Supabase DB에 실제로 쓴다."""

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.config import settings
from app.db import engine
from app.deps import get_current_user
from app.errors import register_error_handlers
from app.models import User
from app.security import create_access_token, verify_password

from .conftest import new_email


def signup_payload(**override) -> dict:
    payload = {
        "email": new_email(),
        "password": "password1234",
        "nickname": "망원동자취생",
        "lat": 37.5563,
        "lng": 126.9019,
    }
    payload.update(override)
    return payload


def row(user_id: int):
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT * FROM users WHERE id = :id"), {"id": user_id}
        ).one()


# ---------- A-01 회원가입 ----------


def test_signup_success_stores_rounded_location_and_hash(client: TestClient):
    # 이메일은 대소문자를 섞어 보내도 소문자로 저장된다.
    payload = signup_payload(email=new_email().replace("pytest-", "PyTest-"))
    res = client.post("/auth/signup", json=payload)
    assert res.status_code == 201
    assert list(res.json()) == ["id"]

    saved = row(res.json()["id"])
    assert saved.email == payload["email"].lower()
    assert (
        float(saved.lat) == 37.56 and float(saved.lng) == 126.90
    )  # 소수점 2자리로 반올림
    assert saved.password_hash != payload["password"]  # 평문 저장 금지
    assert saved.password_hash.startswith("$2")  # bcrypt
    assert verify_password(payload["password"], saved.password_hash)


def test_signup_duplicate_email_is_409_even_with_different_case(client: TestClient):
    payload = signup_payload()
    assert client.post("/auth/signup", json=payload).status_code == 201
    for email in (payload["email"], payload["email"].upper()):
        res = client.post("/auth/signup", json={**payload, "email": email})
        assert res.status_code == 409
        assert res.json() == {
            "code": "EMAIL_TAKEN",
            "message": "이미 가입된 이메일이에요",
        }


def test_signup_allows_duplicate_nickname(client: TestClient):
    first = client.post("/auth/signup", json=signup_payload(nickname="같은닉네임"))
    second = client.post("/auth/signup", json=signup_payload(nickname="같은닉네임"))
    assert first.status_code == second.status_code == 201


@pytest.mark.parametrize(
    "override, field",
    [
        ({"password": "short"}, "password"),
        ({"password": "a" * 73}, "password"),  # bcrypt는 72바이트까지만 본다
        ({"password": "한" * 25}, "password"),  # 25자지만 75바이트
        ({"email": "not-an-email"}, "email"),
        ({"nickname": "a"}, "nickname"),
        ({"nickname": "a" * 21}, "nickname"),
        ({"nickname": "   "}, "nickname"),
        ({"lat": 91}, "lat"),
        ({"lng": 181}, "lng"),
        ({"lat": "abc"}, "lat"),
    ],
)
def test_signup_invalid_input_is_400_with_field(client: TestClient, override, field):
    res = client.post("/auth/signup", json=signup_payload(**override))
    assert res.status_code == 400
    body = res.json()
    assert body["code"] == "INVALID_INPUT"
    assert body["field"] == field
    assert body[
        "message"
    ]  # 영어 라이브러리 메시지가 아니라 사람이 읽을 문구가 있어야 한다


def test_signup_missing_field_is_400(client: TestClient):
    payload = signup_payload()
    del payload["nickname"]
    res = client.post("/auth/signup", json=payload)
    assert res.status_code == 400
    assert res.json()["field"] == "nickname"


def test_signup_72_byte_password_is_allowed(client: TestClient):
    assert (
        client.post("/auth/signup", json=signup_payload(password="a" * 72)).status_code
        == 201
    )


# ---------- A-02 로그인 ----------


def login(client: TestClient, email: str, password: str = "password1234"):
    return client.post("/auth/login", json={"email": email, "password": password})


def test_login_success_returns_token_and_user(client: TestClient):
    payload = signup_payload()
    user_id = client.post("/auth/signup", json=payload).json()["id"]

    res = login(client, payload["email"].upper())  # 이메일 대소문자는 구분하지 않는다
    assert res.status_code == 200
    body = res.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 24 * 3600
    assert body["user"] == {
        "id": user_id,
        "nickname": "망원동자취생",
        "lat": 37.56,
        "lng": 126.9,
    }

    claims = jwt.decode(body["access_token"], settings.jwt_secret, algorithms=["HS256"])
    assert set(claims) == {"sub", "exp"}  # 토큰에는 id와 만료 시각만 담는다
    assert claims["sub"] == str(user_id)
    remaining = datetime.fromtimestamp(claims["exp"], timezone.utc) - datetime.now(
        timezone.utc
    )
    assert timedelta(hours=23, minutes=59) < remaining <= timedelta(hours=24)


def test_login_failures_look_identical(client: TestClient):
    payload = signup_payload()
    client.post("/auth/signup", json=payload)
    wrong_password = login(client, payload["email"], "wrong-password")
    unknown_email = login(client, new_email("none-"))
    for res in (wrong_password, unknown_email):
        assert res.status_code == 401
        assert res.json() == {
            "code": "INVALID_CREDENTIALS",
            "message": "이메일 또는 비밀번호가 맞지 않아요",
        }
    assert wrong_password.json() == unknown_email.json()  # 가입 여부를 알 수 없다


def test_login_overlong_password_is_just_invalid_credentials(client: TestClient):
    payload = signup_payload()
    client.post("/auth/signup", json=payload)
    assert login(client, payload["email"], "a" * 200).status_code == 401


# ---------- 인증 의존성 ----------


def protected_client() -> TestClient:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/whoami")
    def whoami(user: User = Depends(get_current_user)):
        return {"id": user.id, "nickname": user.nickname}

    return TestClient(app)


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_protected_accepts_valid_token(client: TestClient):
    user_id = client.post("/auth/signup", json=signup_payload()).json()["id"]
    res = protected_client().get(
        "/whoami", headers=bearer(create_access_token(user_id))
    )
    assert res.status_code == 200
    assert res.json()["id"] == user_id


@pytest.mark.parametrize(
    "case",
    [
        "no_header",
        "garbage",
        "expired",
        "wrong_secret",
        "no_exp",
        "deleted_user",
        "not_bearer",
    ],
)
def test_protected_rejects_bad_tokens_with_unauthorized(client: TestClient, case: str):
    user_id = client.post("/auth/signup", json=signup_payload()).json()["id"]
    now = datetime.now(timezone.utc)
    headers: dict = {}
    if case == "garbage":
        headers = bearer("not.a.jwt")
    elif case == "expired":
        token = jwt.encode(
            {"sub": str(user_id), "exp": now - timedelta(seconds=1)},
            settings.jwt_secret,
            "HS256",
        )
        headers = bearer(token)
    elif case == "wrong_secret":
        token = jwt.encode(
            {"sub": str(user_id), "exp": now + timedelta(hours=1)},
            "another-secret-key-of-32-bytes!!",
            "HS256",
        )
        headers = bearer(token)
    elif case == "no_exp":
        headers = bearer(
            jwt.encode({"sub": str(user_id)}, settings.jwt_secret, "HS256")
        )
    elif case == "deleted_user":
        headers = bearer(create_access_token(2**62))  # 존재하지 않는 id
    elif case == "not_bearer":
        headers = {"Authorization": f"Basic {create_access_token(user_id)}"}

    res = protected_client().get("/whoami", headers=headers)
    assert res.status_code == 401
    assert res.json() == {"code": "UNAUTHORIZED", "message": "다시 로그인해 주세요"}
