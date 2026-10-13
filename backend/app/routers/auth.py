from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.errors import AppError
from app.models import User
from app.schemas import (
    LoginRequest,
    LoginResponse,
    SignupRequest,
    SignupResponse,
    UserOut,
    round_coord,
)
from app.security import create_access_token, dummy_hash, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", status_code=201, response_model=SignupResponse)
def signup(body: SignupRequest, db: Session = Depends(get_db)) -> SignupResponse:
    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        nickname=body.nickname,
        lat=round_coord(body.lat),
        lng=round_coord(body.lng),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # 이메일 UNIQUE 위반이 이 INSERT에서 날 수 있는 유일한 제약 오류다.
        # 미리 SELECT로 확인하지 않고 DB 제약에 맡겨 동시 가입에서도 안전하다.
        db.rollback()
        raise AppError("EMAIL_TAKEN")
    return SignupResponse(id=user.id)


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    user = db.scalar(select(User).where(User.email == body.email))
    # 이메일이 없어도 해시 검증을 똑같이 수행해 응답 시간으로 가입 여부를 알 수 없게 한다.
    ok = verify_password(body.password, user.password_hash if user else dummy_hash())
    if user is None or not ok:
        raise AppError("INVALID_CREDENTIALS")
    if user.status == "SUSPENDED":  # 비밀번호가 맞은 사람에게만 알려 정지 여부가 새지 않게 한다
        raise AppError("ACCOUNT_SUSPENDED")
    return LoginResponse(
        access_token=create_access_token(user.id),
        expires_in=settings.jwt_expire_hours * 3600,
        user=UserOut(
            id=user.id, nickname=user.nickname, lat=float(user.lat), lng=float(user.lng)
        ),
    )
