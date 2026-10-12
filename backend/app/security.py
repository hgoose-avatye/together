"""비밀번호 해시(bcrypt)와 액세스 토큰(JWT). 토큰에는 sub(사용자 id)와 exp만 담는다."""

from datetime import datetime, timedelta, timezone
from functools import cache

import bcrypt
import jwt

from app.config import settings

ALGORITHM = "HS256"
MAX_PASSWORD_BYTES = 72  # bcrypt는 72바이트를 넘는 입력을 잘라 버린다.


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    if len(password.encode()) > MAX_PASSWORD_BYTES:
        return False
    return bcrypt.checkpw(password.encode(), password_hash.encode())


@cache
def dummy_hash() -> str:
    """없는 이메일로 로그인할 때도 해시 검증 시간을 똑같이 쓰기 위한 값."""
    return hash_password("not-a-real-password")


def create_access_token(user_id: int) -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expire_hours)
    return jwt.encode({"sub": str(user_id), "exp": exp}, settings.jwt_secret, ALGORITHM)


def decode_access_token(token: str) -> int | None:
    """유효하면 사용자 id, 위조·만료·형식 오류면 None."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[ALGORITHM],
            options={"require": ["sub", "exp"]},
        )
        return int(payload["sub"])
    except (jwt.InvalidTokenError, ValueError):
        return None
