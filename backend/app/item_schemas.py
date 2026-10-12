"""글(items) 요청·응답 스키마. 규칙은 기획서 5.3."""

import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator
from pydantic_core.core_schema import ValidationInfo

from app.config import settings

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
    total_slots: int  # 이웃에게 나눌 몫 수 = 나 포함 인원 - 1
    total_price: int
    deadline: datetime
    pickup_note: str
    product_url: str | None = None
    image_url: str | None = None
    lat: float | None = None
    # 생략돼도 검증 함수가 돌게 해서 "위도만 보낸" 요청을 잡는다(pydantic은 기본값을 검증하지 않는다).
    lng: float | None = Field(default=None, validate_default=True)

    @field_validator("type")
    @classmethod
    def check_type(cls, v: str) -> str:
        # 나눔(SHARE)은 나눔 묶음(Should)에서 추가한다.
        if v != "GROUP_BUY":
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
    def check_slots(cls, v: int) -> int:
        if not 1 <= v <= 20:
            raise ValueError("인원은 나 포함 2~21명이어야 해요")
        return v

    @field_validator("total_price")
    @classmethod
    def check_price(cls, v: int) -> int:
        if not 0 <= v <= 1_000_000:
            raise ValueError("총 가격은 0원 이상 1,000,000원 이하여야 해요")
        return v

    @field_validator("deadline")
    @classmethod
    def check_deadline(cls, v: datetime) -> datetime:
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
