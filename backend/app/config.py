from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Supabase 풀러 세션 모드(5432) 연결 문자열
    database_url: str
    jwt_secret: str
    jwt_expire_hours: int = 24
    # 쉼표로 구분한 허용 출처. 배포 시 프론트 주소를 추가한다.
    cors_origins: str = "http://localhost:5173"
    supabase_url: str = ""
    supabase_service_key: str = ""
    supabase_bucket: str = "images"
    # 운영 서버는 production으로 둔다. DB 보호 검증(dbguard)은 development만 통과시킨다.
    app_env: str = "development"
    # 인증 메일 발송 방식: console(개발: 서버 콘솔에 링크 출력) 또는 smtp(운영). 기획서 5.10
    mail_backend: str = "console"
    frontend_url: str = "http://localhost:5173"  # 메일 링크의 앞부분
    smtp_host: str = ""
    smtp_port: int = 587
    # 암호화 연결(STARTTLS). Gmail 같은 외부 SMTP는 켜 두고, 암호화를 지원하지 않는 로컬 Mailpit만 끈다.
    smtp_starttls: bool = True
    smtp_user: str = ""
    smtp_password: str = ""
    mail_from: str = ""

    @field_validator("database_url")
    @classmethod
    def use_psycopg_driver(cls, v: str) -> str:
        # Supabase가 주는 postgresql:// 주소를 psycopg 3 드라이버 주소로 바꾼다.
        for prefix in ("postgresql://", "postgres://"):
            if v.startswith(prefix):
                return "postgresql+psycopg://" + v[len(prefix) :]
        return v

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]



def check_runtime(s: Settings) -> None:
    """서버 시작 때 설정이 위험하거나 모순되면 거부한다(fail closed, 기획서 5.10)."""
    if s.mail_backend not in ("console", "smtp"):
        raise RuntimeError(f"MAIL_BACKEND={s.mail_backend!r}: console 또는 smtp여야 합니다")
    if s.app_env == "production" and s.mail_backend == "console":
        raise RuntimeError("운영 환경에서는 MAIL_BACKEND=console을 쓸 수 없습니다(인증 링크가 서버 로그에만 남음)")
    if s.mail_backend == "smtp" and not (s.smtp_host and s.mail_from):
        raise RuntimeError("MAIL_BACKEND=smtp에는 SMTP_HOST와 MAIL_FROM이 필요합니다")
    # 비밀번호를 평문으로 보내지 않게 한다: 암호화 없이 로그인해야 하는 설정은 로컬 서버에만 허용
    if s.mail_backend == "smtp" and not s.smtp_starttls and s.smtp_host not in ("localhost", "127.0.0.1"):
        raise RuntimeError("SMTP_STARTTLS=false는 로컬 SMTP 서버(localhost)에서만 쓸 수 있습니다")


settings = Settings()
