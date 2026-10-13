"""기획서 7장 엔티티 설계. 제약 이름은 마이그레이션과 같아야 한다."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE', 'SUSPENDED')", name="status"),
        CheckConstraint(
            "(status = 'SUSPENDED') = (suspended_at IS NOT NULL)",
            name="suspended_consistency",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    nickname: Mapped[str] = mapped_column(String(20))
    lat: Mapped[Decimal] = mapped_column(Numeric(4, 2))
    lng: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    status: Mapped[str] = mapped_column(String(10), server_default="ACTIVE")
    suspended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    suspension_reason: Mapped[str | None] = mapped_column(String(500))
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Item(Base):
    __tablename__ = "items"
    __table_args__ = (
        CheckConstraint("type IN ('GROUP_BUY', 'SHARE')", name="type"),
        CheckConstraint(
            "category IN ('FRUIT_VEG', 'FOOD', 'HOUSEHOLD', 'ETC')", name="category"
        ),
        CheckConstraint("total_slots BETWEEN 1 AND 20", name="total_slots"),
        CheckConstraint("total_price >= 0", name="total_price"),
        CheckConstraint(
            "filled_slots >= 0 AND filled_slots <= total_slots", name="filled_slots"
        ),
        CheckConstraint(
            "status IN ('OPEN', 'CONFIRMED', 'FAILED', 'CANCELED')", name="status"
        ),
        CheckConstraint(
            "type <> 'SHARE' OR (total_slots = 1 AND total_price = 0 AND image_url IS NOT NULL)",
            name="share_rule",
        ),
        Index(None, "status", "deadline"),
        Index(None, "owner_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    type: Mapped[str] = mapped_column(String(10))
    category: Mapped[str] = mapped_column(String(10), server_default="ETC")
    title: Mapped[str] = mapped_column(String(50))
    total_slots: Mapped[int] = mapped_column(Integer)
    total_price: Mapped[int] = mapped_column(Integer)
    price_per_slot: Mapped[int] = mapped_column(Integer)
    filled_slots: Mapped[int] = mapped_column(Integer, server_default="0")
    deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    lat: Mapped[Decimal] = mapped_column(Numeric(4, 2))
    lng: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    pickup_note: Mapped[str] = mapped_column(String(200))
    product_url: Mapped[str | None] = mapped_column(String(500))
    image_url: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(10), server_default="OPEN")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Reservation(Base):
    __tablename__ = "reservations"
    __table_args__ = (
        UniqueConstraint("item_id", "user_id"),
        Index(None, "user_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    item_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("items.id"))
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Report(Base):
    """신고. 접수만 하고 자동 제재는 하지 않는다(기획서 5.9)."""

    __tablename__ = "reports"
    __table_args__ = (
        UniqueConstraint("reporter_id", "target_user_id", "item_id"),
        CheckConstraint(
            "reason IN ('INAPPROPRIATE', 'FRAUD', 'THREAT', 'OTHER')", name="reason"
        ),
        CheckConstraint("status IN ('OPEN', 'RESOLVED')", name="status"),
        CheckConstraint(
            "resolution IS NULL OR resolution IN ('DISMISSED', 'SUSPENDED')",
            name="resolution",
        ),
        CheckConstraint("reporter_id <> target_user_id", name="self_report"),
        CheckConstraint(
            "reason <> 'OTHER' OR length(btrim(detail)) > 0", name="other_needs_detail"
        ),
        CheckConstraint(
            "(status = 'OPEN' AND resolution IS NULL AND resolved_at IS NULL) OR "
            "(status = 'RESOLVED' AND resolution IS NOT NULL AND resolved_at IS NOT NULL)",
            name="resolved_consistency",
        ),
        Index(None, "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    reporter_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    target_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    item_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("items.id"))
    reason: Mapped[str] = mapped_column(String(20))
    detail: Mapped[str] = mapped_column(String(500), server_default="")
    status: Mapped[str] = mapped_column(String(10), server_default="OPEN")
    resolution: Mapped[str | None] = mapped_column(String(10))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_note: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class AdminAction(Base):
    """운영 도구가 남기는 감사 기록. 추가만 하고 고치거나 지우지 않는다(기획서 5.9)."""

    __tablename__ = "admin_actions"
    __table_args__ = (
        CheckConstraint(
            "action IN ('SUSPEND', 'UNSUSPEND', 'RESOLVE_REPORT', 'VERIFY_EMAIL')",
            name="action",
        ),
        Index(None, "target_user_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    action: Mapped[str] = mapped_column(String(20))
    target_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    report_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("reports.id"))
    actor_os_user: Mapped[str] = mapped_column(String(100))
    note: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class EmailVerificationToken(Base):
    """이메일 인증 토큰. 원문은 저장하지 않고 SHA-256 해시만 둔다(기획서 5.10)."""

    __tablename__ = "email_verification_tokens"
    __table_args__ = (
        CheckConstraint("length(token_hash) = 64", name="token_hash_len"),
        Index(None, "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
