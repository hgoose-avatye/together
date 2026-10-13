"""backend/.env의 DATABASE_URL과 JWT_SECRET을 채우고 DB 연결을 확인한다.

실행: cd backend && uv run python scripts/setup_env.py
다른 프로젝트(배포용 등)는 연결 문자열을 인자로 준다:
  uv run python scripts/setup_env.py "postgresql://...:[YOUR-PASSWORD]@...:5432/postgres"
비밀번호는 화면에 보이지 않고, 특수문자는 자동으로 퍼센트 인코딩한다.

사진 저장소 설정(SUPABASE_URL, SUPABASE_SERVICE_KEY)과 버킷 확인:
  uv run python scripts/setup_env.py storage
SUPABASE_URL은 DATABASE_URL의 프로젝트 ID로 자동으로 만든다.

인증 메일 설정(기획서 5.10). 비밀 값은 화면에 보이지 않게 입력받는다:
  uv run python scripts/setup_env.py mail console   # 서버 콘솔에 링크 출력(기본)
  uv run python scripts/setup_env.py mail mailpit   # 로컬 Mailpit(SMTP 1025, 웹 http://localhost:8025)
  uv run python scripts/setup_env.py mail gmail     # Gmail SMTP. 앱 비밀번호가 필요하다(개발·시연 전용)
"""

import getpass
import re
import secrets
import shutil
import sys
from pathlib import Path
from urllib.parse import quote

import httpx
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


def get_value(lines: list[str], key: str) -> str:
    return next((l.split("=", 1)[1] for l in lines if l.startswith(f"{key}=")), "")


def setup_storage() -> None:
    lines = ENV.read_text().splitlines()
    m = re.search(r"//postgres\.([a-z0-9]+):", get_value(lines, "DATABASE_URL"))
    if not m:
        sys.exit(
            "DATABASE_URL에서 프로젝트 ID를 찾지 못했습니다. DB 설정부터 실행해 주세요."
        )
    url = f"https://{m.group(1)}.supabase.co"
    bucket = get_value(lines, "SUPABASE_BUCKET") or "images"
    print(f"SUPABASE_URL: {url}")
    print(
        "Supabase > Project Settings > API Keys > Secret keys(sb_secret_...)를 붙여 넣으세요."
    )

    key = ""
    while not key:
        key = getpass.getpass("Secret key (붙여 넣어도 보이지 않음): ").strip()
    if not key.startswith(("sb_secret_", "eyJ")):
        sys.exit(
            "Secret key 형식이 아닙니다(sb_secret_로 시작). Publishable key를 넣지 않았는지 확인해 주세요."
        )

    print(f"버킷 '{bucket}' 확인 중...")
    r = httpx.get(
        f"{url}/storage/v1/bucket/{bucket}",
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
        timeout=15,
    )
    if r.status_code != 200:
        sys.exit(
            f"버킷 확인 실패({r.status_code}). .env는 바꾸지 않았습니다.\n{r.text[:200]}"
        )
    b = r.json()
    print(
        f"버킷 확인: 공개={b.get('public')}, 크기 제한={b.get('file_size_limit')}, "
        f"형식={b.get('allowed_mime_types')}"
    )

    lines = set_line(lines, "SUPABASE_URL", url)
    lines = set_line(lines, "SUPABASE_SERVICE_KEY", key)
    lines = set_line(lines, "SUPABASE_BUCKET", bucket)
    ENV.write_text("\n".join(lines) + "\n")
    print("저장 완료. backend/.env를 저장했습니다.")


MAIL_KEYS = ("MAIL_BACKEND", "SMTP_HOST", "SMTP_PORT", "SMTP_STARTTLS", "SMTP_USER", "SMTP_PASSWORD", "MAIL_FROM")


def setup_mail(kind: str) -> None:
    """메일 설정 값을 .env에 쓴다. 다른 메일 값은 지워 이전 설정이 남지 않게 한다."""
    if kind == "console":
        values = {"MAIL_BACKEND": "console"}
    elif kind == "mailpit":
        values = {"MAIL_BACKEND": "smtp", "SMTP_HOST": "localhost", "SMTP_PORT": "1025", "SMTP_STARTTLS": "false", "MAIL_FROM": "같이 <no-reply@gachi.local>"}
    elif kind == "gmail":
        addr = input("Gmail 주소: ").strip()
        if not re.fullmatch(r"[^@\s]+@gmail\.com", addr):
            sys.exit("Gmail 주소가 아닙니다. .env는 바꾸지 않았습니다.")
        print("Google 계정 > 보안 > 2단계 인증을 켠 뒤 '앱 비밀번호'를 만들어 붙여 넣으세요(16자리, 공백은 무시).")
        pw = ""
        while not pw:
            pw = getpass.getpass("앱 비밀번호 (입력해도 보이지 않음): ").replace(" ", "").strip()
        if len(pw) != 16:
            sys.exit("앱 비밀번호는 16자리입니다. 로그인 비밀번호가 아닌지 확인해 주세요. .env는 바꾸지 않았습니다.")
        values = {"MAIL_BACKEND": "smtp", "SMTP_HOST": "smtp.gmail.com", "SMTP_PORT": "587", "SMTP_STARTTLS": "true", "SMTP_USER": addr, "SMTP_PASSWORD": pw, "MAIL_FROM": addr}
    else:
        sys.exit("mail 뒤에는 console, mailpit, gmail 중 하나를 쓰세요.")
    lines = [l for l in ENV.read_text().splitlines() if l.split("=", 1)[0] not in MAIL_KEYS]
    for key, value in values.items():
        lines = set_line(lines, key, value)
    ENV.write_text("\n".join(lines) + "\n")
    print(f"저장 완료. 메일 방식: {kind}. 서버를 다시 시작하면 적용됩니다.")


def main() -> None:
    if not ENV.exists():
        shutil.copy(EXAMPLE, ENV)

    if len(sys.argv) > 2 and sys.argv[1] == "mail":
        setup_mail(sys.argv[2])
        return

    if len(sys.argv) > 1 and sys.argv[1] == "storage":
        setup_storage()
        return

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
