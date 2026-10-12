"""backend/.env의 DATABASE_URL과 JWT_SECRET을 채우고 DB 연결을 확인한다.

실행: cd backend && uv run python scripts/setup_env.py
다른 프로젝트(배포용 등)는 연결 문자열을 인자로 준다:
  uv run python scripts/setup_env.py "postgresql://...:[YOUR-PASSWORD]@...:5432/postgres"
비밀번호는 화면에 보이지 않고, 특수문자는 자동으로 퍼센트 인코딩한다.
"""

import getpass
import secrets
import shutil
import sys
from pathlib import Path
from urllib.parse import quote

import psycopg

ENV = Path(__file__).resolve().parents[1] / ".env"
EXAMPLE = ENV.with_name(".env.example")
DEFAULT_URL = (
    "postgresql://postgres.ruizsrgsebyjwxeswtwd:[YOUR-PASSWORD]"
    "@aws-0-ap-northeast-2.pooler.supabase.com:5432/postgres"
)


def set_line(lines: list[str], key: str, value: str) -> list[str]:
    out = [f"{key}={value}" if line.startswith(f"{key}=") else line for line in lines]
    if not any(line.startswith(f"{key}=") for line in lines):
        out.append(f"{key}={value}")
    return out


def main() -> None:
    if not ENV.exists():
        shutil.copy(EXAMPLE, ENV)

    url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL
    if "[YOUR-PASSWORD]" not in url:
        sys.exit(
            "연결 문자열에 [YOUR-PASSWORD] 자리가 없습니다. Supabase에서 복사한 그대로 넣어 주세요."
        )
    print(f"연결할 DB: {url.split('@', 1)[1]}")
    print("영문 입력 상태인지 확인하고 입력하세요.")

    password = ""
    while not password:
        password = getpass.getpass("DB 비밀번호 (입력해도 보이지 않음): ")
        if not password:
            print("비밀번호가 비어 있습니다. 다시 입력해 주세요.")
    full_url = url.replace("[YOUR-PASSWORD]", quote(password, safe=""))

    print("연결 확인 중...")
    try:
        with psycopg.connect(full_url, connect_timeout=10) as conn:
            conn.execute("SELECT 1")
    except psycopg.OperationalError as e:
        msg = str(e)
        if "password authentication failed" in msg:
            sys.exit(
                "비밀번호가 틀렸습니다. .env는 바꾸지 않았습니다. 다시 실행해 주세요."
            )
        sys.exit(f"연결 실패. .env는 바꾸지 않았습니다.\n{msg.splitlines()[0]}")

    lines = ENV.read_text().splitlines()
    lines = set_line(lines, "DATABASE_URL", full_url)
    jwt = next((l.split("=", 1)[1] for l in lines if l.startswith("JWT_SECRET=")), "")
    if not jwt:
        lines = set_line(lines, "JWT_SECRET", secrets.token_urlsafe(48))
    ENV.write_text("\n".join(lines) + "\n")
    print("연결 성공. backend/.env를 저장했습니다.")


if __name__ == "__main__":
    main()
