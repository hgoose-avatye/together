"""개발·테스트 DB 보호 (기획서 5.11).

pytest, 테스트 도구, 시연 스크립트의 DB 변경은 실행 전에 이 검사를 통과해야 한다.
엔진이 실제로 쓰는 연결 URL에서 Supabase 프로젝트 id를 읽어 코드에 커밋된 허용 목록과 비교한다.
별도 환경 변수에 적어 둔 id는 믿지 않고, 읽지 못하거나 목록에 없으면 거부한다(fail closed).
우회 옵션은 없다. 운영 DB를 다루는 admin.py는 이 검사를 쓰지 않는다.
"""

from sqlalchemy.engine import Engine, make_url

from app.config import settings

# 개발용 Supabase 프로젝트(gachi-dev). 개발 프로젝트를 바꿀 때는 이 목록을 코드로 고치고 리뷰받는다.
ALLOWED_PROJECT_IDS = frozenset({"ruizsrgsebyjwxeswtwd"})


class UnsafeDatabase(RuntimeError):
    pass


def project_id(url) -> str | None:
    """Supabase 풀러의 사용자 이름 `postgres.<프로젝트 id>`에서 id를 읽는다. 형식이 다르면 None."""
    user = make_url(url).username if isinstance(url, str) else url.username
    if user and user.startswith("postgres.") and len(user) > len("postgres."):
        return user.split(".", 1)[1]
    return None


def assert_dev_database(engine: Engine, app_env: str | None = None) -> str:
    """개발 DB가 아니면 UnsafeDatabase를 던진다. 통과하면 프로젝트 id를 돌려준다."""
    env = settings.app_env if app_env is None else app_env
    if env != "development":
        raise UnsafeDatabase(f"APP_ENV={env!r}: 개발 환경(development)에서만 실행할 수 있습니다")
    pid = project_id(engine.url)
    if pid is None:
        raise UnsafeDatabase("연결 URL에서 프로젝트 id를 읽을 수 없어 실행을 거부합니다")
    if pid not in ALLOWED_PROJECT_IDS:
        raise UnsafeDatabase(f"프로젝트 {pid}는 개발 DB 허용 목록에 없어 실행을 거부합니다")
    return pid
