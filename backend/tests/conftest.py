import os
import uuid
from pathlib import Path

import pytest

# .env가 없을 때만 가짜 값을 넣어 DB가 필요 없는 테스트를 돌린다.
# .env가 있으면 그 값(Supabase 개발 DB)을 그대로 쓴다.
if not (Path(__file__).resolve().parents[1] / ".env").exists():
    os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
    os.environ.setdefault("JWT_SECRET", "test-secret")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db import engine  # noqa: E402
from app.main import app  # noqa: E402

TEST_EMAIL_PREFIX = "pytest-"


def _purge_test_data() -> None:
    """테스트가 만든 데이터를 지운다. 테스트 계정은 이메일이 pytest-로 시작한다."""
    users = f"SELECT id FROM users WHERE email LIKE '{TEST_EMAIL_PREFIX}%'"
    items = f"SELECT id FROM items WHERE owner_id IN ({users})"
    with engine.begin() as conn:
        conn.execute(
            text(
                f"DELETE FROM reservations WHERE user_id IN ({users}) OR item_id IN ({items})"
            )
        )
        conn.execute(text(f"DELETE FROM items WHERE owner_id IN ({users})"))
        conn.execute(text(f"DELETE FROM users WHERE email LIKE '{TEST_EMAIL_PREFIX}%'"))


@pytest.fixture(scope="session", autouse=True)
def clean_test_data():
    """이전 실행이 남긴 데이터를 먼저 지우고, 끝나면 이번 실행의 데이터를 지운다."""
    if (Path(__file__).resolve().parents[1] / ".env").exists():
        _purge_test_data()
        yield
        _purge_test_data()
    else:
        yield


@pytest.fixture(scope="session")
def client() -> TestClient:
    return TestClient(app)


def new_email(tag: str = "") -> str:
    return f"{TEST_EMAIL_PREFIX}{tag}{uuid.uuid4().hex[:12]}@example.com"
