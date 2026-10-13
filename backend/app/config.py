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


settings = Settings()
