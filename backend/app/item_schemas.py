"""글(items) 요청·응답 스키마. 규칙은 기획서 5.3."""

import re
from typing import NamedTuple
from datetime import date, datetime, time, timedelta, timezone
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator
from pydantic_core.core_schema import ValidationInfo

from app.config import settings
from app.errors import invalid_input

CATEGORIES = ("FRUIT_VEG", "FOOD", "HOUSEHOLD", "ETC")
MAX_DEADLINE_DAYS = 30
KST = timezone(timedelta(hours=9))  # 한국은 서머타임이 없어 고정 오프셋으로 충분하다

_UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"


def own_image_pattern() -> re.Pattern[str]:
    """우리 Storage 버킷의 `{UUID}.{jpg,png,webp}` 형식 전체와 일치하는 주소만 허용한다."""
    base = re.escape(settings.supabase_url.rstrip("/"))
    bucket = re.escape(settings.supabase_bucket)
    return re.compile(
        rf"^{base}/storage/v1/object/public/{bucket}/{_UUID}\.(jpg|png|webp)$"
    )


class ItemCreate(BaseModel):
    type: str
    category: str = "ETC"
    title: str
    # 같이사기는 셋 다 필수. 나눔은 total_slots, total_price, deadline을 받아도 무시하고 expiry_date로 정한다.
    # 필수 여부는 resolve()가 유형별로 검사한다.
    total_slots: int | None = None  # 이웃에게 나눌 몫 수 = 나 포함 인원 - 1
    total_price: int | None = None
    deadline: datetime | None = None
    expiry_date: date | None = None  # 나눔: 유통기한 날짜
    pickup_note: str
    product_url: str | None = None
    image_url: str | None = None
    lat: float | None = None
    # 생략돼도 검증 함수가 돌게 해서 "위도만 보낸" 요청을 잡는다(pydantic은 기본값을 검증하지 않는다).
    lng: float | None = Field(default=None, validate_default=True)

    @field_validator("type")
    @classmethod
    def check_type(cls, v: str) -> str:
        if v not in ("GROUP_BUY", "SHARE"):
            raise ValueError("지원하지 않는 글 유형이에요")
        return v

    @field_validator("category")
    @classmethod
    def check_category(cls, v: str) -> str:
        if v not in CATEGORIES:
            raise ValueError("분류가 올바르지 않아요")
        return v

    @field_validator("title")
    @classmethod
    def check_title(cls, v: str) -> str:
        v = v.strip()
        if not 1 <= len(v) <= 50:
            raise ValueError("제목은 1~50자로 입력해 주세요")
        return v

    @field_validator("total_slots")
    @classmethod
    def check_slots(cls, v: int | None, info: ValidationInfo) -> int | None:
        if info.data.get("type") == "SHARE":
            return v  # 나눔은 보내도 무시한다
        if v is not None and not 1 <= v <= 20:
            raise ValueError("인원은 나 포함 2~21명이어야 해요")
        return v

    @field_validator("total_price")
    @classmethod
    def check_price(cls, v: int | None, info: ValidationInfo) -> int | None:
        if info.data.get("type") == "SHARE":
            return v
        if v is not None and not 0 <= v <= 1_000_000:
            raise ValueError("총 가격은 0원 이상 1,000,000원 이하여야 해요")
        return v

    @field_validator("deadline")
    @classmethod
    def check_deadline(cls, v: datetime | None, info: ValidationInfo) -> datetime | None:
        if v is None or info.data.get("type") == "SHARE":
            return v
        if v.tzinfo is None:
            raise ValueError("마감 시각에 시간대가 필요해요")
        now = datetime.now(timezone.utc)
        if v <= now:
            raise ValueError("마감 시각은 지금 이후여야 해요")
        if v > now + timedelta(days=MAX_DEADLINE_DAYS):
            raise ValueError(f"마감 시각은 {MAX_DEADLINE_DAYS}일 이내여야 해요")
        return v

    @field_validator("pickup_note")
    @classmethod
    def check_pickup_note(cls, v: str) -> str:
        v = v.strip()
        if not 1 <= len(v) <= 200:
            raise ValueError("만남 장소 메모를 1~200자로 적어 주세요")
        return v

    @field_validator("product_url")
    @classmethod
    def check_product_url(cls, v: str | None) -> str | None:
        v = (v or "").strip()
        if not v:
            return None
        parsed = urlparse(v)
        if (
            len(v) > 500
            or parsed.scheme not in ("http", "https")
            or not parsed.netloc
            or " " in v
        ):
            raise ValueError("상품 링크는 http 또는 https 주소여야 해요")
        return v

    @field_validator("image_url")
    @classmethod
    def check_image_url(cls, v: str | None) -> str | None:
        v = (v or "").strip()
        if not v:
            return None
        if not settings.supabase_url or not own_image_pattern().match(v):
            raise ValueError("사진 주소가 올바르지 않아요")
        return v

    @field_validator("lat")
    @classmethod
    def check_lat(cls, v: float | None) -> float | None:
        if v is not None and not -90 <= v <= 90:
            raise ValueError("위도가 올바르지 않아요")
        return v

    @field_validator("lng")
    @classmethod
    def check_lng(cls, v: float | None, info: ValidationInfo) -> float | None:
        if v is not None and not -180 <= v <= 180:
            raise ValueError("경도가 올바르지 않아요")
        if "lat" in info.data and (v is None) != (info.data["lat"] is None):
            raise ValueError("위도와 경도를 함께 보내 주세요")
        return v


    def resolve(self) -> "ResolvedItem":
        """유형별 규칙을 적용해 저장할 값을 정한다(기획서 5.3). 위반하면 field가 붙은 INVALID_INPUT."""
        if self.type == "SHARE":
            if self.expiry_date is None:
                raise invalid_input("유통기한 날짜를 입력해 주세요", "expiry_date")
            today = datetime.now(KST).date()
            if not today <= self.expiry_date <= today + timedelta(days=MAX_DEADLINE_DAYS):
                raise invalid_input(
                    f"유통기한은 오늘부터 {MAX_DEADLINE_DAYS}일 이내여야 해요", "expiry_date"
                )
            if self.image_url is None:
                raise invalid_input("나눔에는 사진이 필요해요", "image_url")
            if self.product_url is not None:
                raise invalid_input("나눔에는 상품 링크를 붙일 수 없어요", "product_url")
            # 몫 1개, 0원은 서버가 정한다. 마감은 유통기한 다음 날 00:00(KST)부터 신청 불가.
            return ResolvedItem(
                1, 0, datetime.combine(self.expiry_date + timedelta(days=1), time(0), KST)
            )
        for name, label in (
            ("total_slots", "인원을 입력해 주세요"),
            ("total_price", "총 가격을 입력해 주세요"),
            ("deadline", "마감 시각을 입력해 주세요"),
        ):
            if getattr(self, name) is None:
                raise invalid_input(label, name)
        return ResolvedItem(self.total_slots, self.total_price, self.deadline)


class ResolvedItem(NamedTuple):
    total_slots: int
    total_price: int
    deadline: datetime


class ItemOut(BaseModel):
    """목록(A-03)과 같은 항목 형식. pickup_note는 넣지 않는다."""

    id: int
    type: str
    category: str
    title: str
    owner_nickname: str
    total_slots: int
    filled_slots: int
    remaining_slots: int
    total_price: int
    price_per_slot: int
    deadline: datetime
    distance_km: float
    status: str
    is_mine: bool
    is_joined: bool
    image_url: str | None
    product_url: str | None


class ItemDetailOut(ItemOut):
    """작성자 본인에게만 돌려주는 형식(A-04 응답)."""

    pickup_note: str
    owner_share: int


class ItemListOut(BaseModel):
    items: list[ItemOut]


class JoinOut(BaseModel):
    """몫 신청(A-05) 결과. status는 신청 직후의 저장값(OPEN 또는 마지막 몫이면 CONFIRMED)."""

    reservation_id: int
    item_id: int
    filled_slots: int
    total_slots: int
    remaining_slots: int
    status: str


class ReservedItemOut(BaseModel):
    id: int
    type: str
    title: str
    owner_nickname: str
    price_per_slot: int
    deadline: datetime
    status: str
    pickup_note: str | None  # 성사(CONFIRMED)된 글에서만 채운다
    owner_suspended: bool  # 개설자 계정이 지금 정지 상태인지(사유는 주지 않는다)


class ReservationOut(BaseModel):
    reservation_id: int
    joined_at: datetime
    item: ReservedItemOut


class ReservationListOut(BaseModel):
    reservations: list[ReservationOut]


class ParticipantOut(BaseModel):
    reservation_id: int  # 신고할 때 대상을 가리키는 값(사용자 id는 주지 않는다)
    nickname: str
    joined_at: datetime
    user_suspended: bool  # 그 참여자 계정이 지금 정지 상태인지(사유는 주지 않는다)


class MyItemOut(BaseModel):
    id: int
    type: str
    title: str
    filled_slots: int
    total_slots: int
    total_price: int
    price_per_slot: int
    owner_share: int
    deadline: datetime
    status: str
    pickup_note: str
    participants: list[ParticipantOut]


class MyItemListOut(BaseModel):
    items: list[MyItemOut]


REPORT_REASONS = ("INAPPROPRIATE", "FRAUD", "THREAT", "OTHER")


class ReportCreate(BaseModel):
    """신고(A-10). 신고 대상(target)은 받지 않는다. 서버가 글과 신청 기록으로 정한다."""

    item_id: int
    reservation_id: int | None = None  # 없으면 글 개설자, 있으면 그 신청의 참여자
    reason: str
    # 생략돼도 검증이 돌게 해서 '기타인데 설명 없음'을 잡는다(pydantic은 기본값을 검증하지 않는다)
    detail: str = Field(default="", validate_default=True)

    @field_validator("reason")
    @classmethod
    def check_reason(cls, v: str) -> str:
        if v not in REPORT_REASONS:
            raise ValueError("신고 사유가 올바르지 않아요")
        return v

    @field_validator("detail")
    @classmethod
    def check_detail(cls, v: str, info: ValidationInfo) -> str:
        v = v.strip()
        if len(v) > 500:
            raise ValueError("설명은 500자 이하로 적어 주세요")
        if info.data.get("reason") == "OTHER" and not v:
            raise ValueError("기타를 고른 경우에는 설명을 적어 주세요")
        return v


class ReportOut(BaseModel):
    id: int
    status: str
