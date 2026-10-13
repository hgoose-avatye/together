"""이메일 소유 확인 (기획서 5.10, A-11, A-12).

토큰은 무작위 불투명 값이고 DB에는 SHA-256 해시만 둔다. 한 번만 쓸 수 있고(조건부 UPDATE),
재발송하면 이전 토큰은 만료시킨다. 메일 링크는 프론트 /verify 화면이 열고 화면이 POST로 확인한다.
"""

import hashlib
import logging
import secrets

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.errors import AppError
from app.mail import send_mail
from app.models import User

log = logging.getLogger("gachi.mail")

TOKEN_TTL_HOURS = 24  # 초안 값(기획서 5.10)
RESEND_MIN_SECONDS = 60  # 초안 값
RESEND_MAX_PER_DAY = 5  # 초안 값
MAX_TOKEN_CHARS = 200

# 유효한 토큰을 한 번만 소비한다. 동시에 같은 링크를 열어도 한 요청만 통과한다.
CONSUME_SQL = text(
    "UPDATE email_verification_tokens SET used_at = now() "
    "WHERE token_hash = :h AND used_at IS NULL AND expires_at > now() RETURNING user_id"
)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _issue_and_send(db: Session, user: User) -> None:
    """새 토큰을 저장하고(이전 토큰은 만료) 메일을 보낸다. 호출자가 사용자 행을 잠근 상태여야 한다."""
    db.execute(
        text(
            "UPDATE email_verification_tokens SET expires_at = now() "
            "WHERE user_id = :u AND used_at IS NULL AND expires_at > now()"
        ),
        {"u": user.id},
    )
    token = secrets.token_urlsafe(32)
    db.execute(
        text(
            "INSERT INTO email_verification_tokens (user_id, token_hash, expires_at) "
            "VALUES (:u, :h, now() + make_interval(hours => :ttl))"
        ),
        {"u": user.id, "h": hash_token(token), "ttl": TOKEN_TTL_HOURS},
    )
    db.commit()  # 메일이 실패해도 토큰은 남지만, 원문을 아는 사람이 없어 쓸 수 없고 재발송으로 대체된다
    link = f"{settings.frontend_url.rstrip('/')}/verify?token={token}"
    send_mail(
        user.email,
        "[같이] 이메일 인증을 완료해 주세요",
        f"아래 링크를 열어 이메일 인증을 완료해 주세요. 링크는 {TOKEN_TTL_HOURS}시간 동안 한 번만 쓸 수 있어요.\n\n{link}\n\n"
        "직접 가입하지 않았다면 이 메일을 무시해 주세요.",
    )


def send_on_signup(db: Session, user: User) -> None:
    """가입 직후 인증 메일. 발송이 실패해도 가입은 성공이다(재발송으로 다시 받을 수 있다)."""
    try:
        _issue_and_send(db, user)
    except Exception:
        db.rollback()
        log.exception("가입 인증 메일 발송 실패 user_id=%s", user.id)


def resend(db: Session, user_id: int) -> bool:
    """재발송(A-12). 인증됐으면 False. 제한을 넘으면 TOO_MANY_REQUESTS."""
    # 같은 계정의 동시 재발송이 제한 검사를 함께 통과하지 못하게 사용자 행을 잠근다
    user = db.get(User, user_id, with_for_update=True)
    if user is None:
        raise AppError("UNAUTHORIZED")
    if user.email_verified_at is not None:
        db.rollback()
        return False
    day_count, too_soon = db.execute(
        text(
            "SELECT count(*), coalesce(bool_or(created_at > now() - make_interval(secs => :s)), false) "
            "FROM email_verification_tokens "
            "WHERE user_id = :u AND created_at > now() - interval '24 hours'"
        ),
        {"u": user_id, "s": RESEND_MIN_SECONDS},
    ).one()
    if too_soon or day_count >= RESEND_MAX_PER_DAY:
        db.rollback()
        raise AppError("TOO_MANY_REQUESTS")
    _issue_and_send(db, user)
    return True


def verify(db: Session, token: str) -> None:
    """A-11. 틀리거나 만료됐거나 이미 쓴 토큰이면 INVALID_TOKEN."""
    if not token or len(token) > MAX_TOKEN_CHARS:
        raise AppError("INVALID_TOKEN")
    row = db.execute(CONSUME_SQL, {"h": hash_token(token)}).first()
    if row is None:
        db.rollback()
        raise AppError("INVALID_TOKEN")
    # 이미 인증된 계정이면 시각을 바꾸지 않는다(멱등)
    db.execute(
        text("UPDATE users SET email_verified_at = COALESCE(email_verified_at, now()) WHERE id = :u"),
        {"u": row.user_id},
    )
    db.commit()
