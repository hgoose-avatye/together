from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import AppError
from app.models import User
from app.security import decode_access_token

# 토큰이 없을 때도 FastAPI 기본 403 대신 우리 에러 형식(UNAUTHORIZED)으로 답하려고 auto_error를 끈다.
bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise AppError("UNAUTHORIZED")
    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise AppError("UNAUTHORIZED")
    user = db.get(User, user_id)
    if user is None:  # 토큰은 유효하지만 탈퇴·삭제된 계정
        raise AppError("UNAUTHORIZED")
    # 요청마다 현재 상태를 읽으므로 정지 전에 받은 토큰도 즉시 막힌다(기획서 5.9).
    if user.status == "SUSPENDED":
        raise AppError("ACCOUNT_SUSPENDED")
    return user


def get_verified_user(user: User = Depends(get_current_user)) -> User:
    """이메일 소유 확인을 마친 사용자만(글 작성 A-04, 몫 신청 A-05). 정지 검사는 get_current_user에서 먼저 한다."""
    if user.email_verified_at is None:
        raise AppError("EMAIL_NOT_VERIFIED")
    return user
