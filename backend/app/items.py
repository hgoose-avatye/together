"""글 응답을 만드는 공통 함수. 목록(A-03), 작성(A-04) 등이 함께 쓴다."""

import logging
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.geo import haversine_km
from app.item_schemas import KST, ItemDetailOut, ItemOut
from app.models import Item, User
from app.pricing import split_price


def display_status(item: Item, now: datetime | None = None) -> str:
    """저장값이 OPEN이어도 마감이 지났으면 FAILED로 보여 준다(기획서 5.4)."""
    now = now or datetime.now(timezone.utc)
    if item.status == "OPEN" and item.deadline <= now:
        return "FAILED"
    return item.status


def distance_to(item: Item, origin: tuple[float, float]) -> float:
    return haversine_km(origin[0], origin[1], float(item.lat), float(item.lng))


def to_item_out(
    item: Item,
    owner: User,
    viewer: User,
    is_joined: bool = False,
    origin: tuple[float, float] | None = None,
) -> ItemOut:
    """origin은 거리 기준점이다. 없으면 보는 사람의 저장 위치를 쓴다."""
    origin = origin or (float(viewer.lat), float(viewer.lng))
    distance = distance_to(item, origin)
    return ItemOut(
        id=item.id,
        type=item.type,
        category=item.category,
        title=item.title,
        owner_nickname=owner.nickname,
        total_slots=item.total_slots,
        filled_slots=item.filled_slots,
        remaining_slots=item.total_slots - item.filled_slots,
        total_price=item.total_price,
        price_per_slot=item.price_per_slot,
        deadline=item.deadline.astimezone(KST),
        distance_km=round(distance, 1),
        status=display_status(item),
        is_mine=item.owner_id == viewer.id,
        is_joined=is_joined,
        image_url=item.image_url,
        product_url=item.product_url,
    )


def to_item_detail(item: Item, owner: User, viewer: User) -> ItemDetailOut:
    """개설자 본인용: pickup_note와 내 부담금(owner_share)을 함께 준다."""
    base = to_item_out(item, owner, viewer)
    _, owner_share = split_price(item.total_price, item.total_slots)
    return ItemDetailOut(
        **base.model_dump(), pickup_note=item.pickup_note, owner_share=owner_share
    )


logger = logging.getLogger(__name__)

# 마감 지난 OPEN 글을 FAILED로 기록한다(기획서 5.4). 여러 번 실행해도 결과가 같다.
FAIL_SQL = text(
    """
    UPDATE items SET status = 'FAILED'
    WHERE id IN (
        SELECT id FROM items
        WHERE status = 'OPEN' AND deadline <= now()
        FOR UPDATE SKIP LOCKED
    )
    """
)


def record_failures(db: Session) -> None:
    """A-06·A-08에서만 부른다. 본 조회 전에 따로 커밋하고, 실패해도 요청은 계속한다.

    SKIP LOCKED라서 다른 요청이 잡은 행은 건너뛰고 기다리지 않는다(다음 조회 때 기록된다).
    기록이 늦어도 응답의 status는 display_status가 FAILED로 보정한다.
    """
    try:
        db.execute(FAIL_SQL)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.warning("무산 기록에 실패했습니다. 요청은 계속합니다.", exc_info=True)
