from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app import email_verification
from app.db import get_db
from app.deps import get_current_user
from app.errors import AppError
from app.models import User
from app.schemas import (
    LoginRequest,
    LoginResponse,
    ResendResponse,
    SignupRequest,
    SignupResponse,
    UserOut,
    VerifyEmailRequest,
    VerifyEmailResponse,
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
    email_verification.send_on_signup(db, user)  # 메일이 실패해도 가입은 성공(재발송 가능)
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
            id=user.id,
            nickname=user.nickname,
            lat=float(user.lat),
            lng=float(user.lng),
            email_verified=user.email_verified_at is not None,
        ),
    )


@router.post("/verify-email", response_model=VerifyEmailResponse)
def verify_email(body: VerifyEmailRequest, db: Session = Depends(get_db)) -> VerifyEmailResponse:
    """인증 링크의 토큰을 확인한다. 로그인이 필요 없다(토큰이 사용자를 가리킨다)."""
    email_verification.verify(db, body.token)
    return VerifyEmailResponse(email_verified=True)


@router.post("/resend-verification", response_model=ResendResponse)
def resend_verification(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ResendResponse:
    return ResendResponse(sent=email_verification.resend(db, user.id))
