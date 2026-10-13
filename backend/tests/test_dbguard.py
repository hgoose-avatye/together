"""개발·테스트 DB 보호 (기획서 5.11). 실제 연결 URL의 프로젝트 id를 코드의 허용 목록과 비교한다."""

import pytest
from sqlalchemy import create_engine

from app.db import engine
from app.dbguard import ALLOWED_PROJECT_IDS, UnsafeDatabase, assert_dev_database, project_id

DEV = next(iter(ALLOWED_PROJECT_IDS))


def eng(user: str):
    # 연결은 하지 않는다(create_engine은 게으르다). URL만 검사한다.
    return create_engine(f"postgresql+psycopg://{user}:pw@aws-0-x.pooler.supabase.com:5432/postgres")


def test_project_id_is_read_from_username():
    assert project_id(eng(f"postgres.{DEV}").url) == DEV
    assert project_id(eng("postgres").url) is None
    assert project_id(eng("postgres.").url) is None
    assert project_id(eng("someone").url) is None


def test_allowed_dev_project_passes():
    assert assert_dev_database(eng(f"postgres.{DEV}"), "development") == DEV


@pytest.mark.parametrize("user", ["postgres.otherproject123", "postgres", "postgres.", "admin"])
def test_other_or_unreadable_project_is_refused(user):
    with pytest.raises(UnsafeDatabase):
        assert_dev_database(eng(user), "development")


@pytest.mark.parametrize("env", ["production", "", "dev", "staging"])
def test_non_development_env_is_refused_even_for_dev_project(env):
    with pytest.raises(UnsafeDatabase):
        assert_dev_database(eng(f"postgres.{DEV}"), env)


def test_the_real_test_engine_passes():
    """pytest가 실제로 쓰는 엔진이 개발 DB임을 확인한다(conftest도 시작할 때 같은 검사를 한다)."""
    assert assert_dev_database(engine) == DEV
