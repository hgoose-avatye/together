from math import cos, radians

from fastapi import APIRouter, Depends, Query
from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.errors import invalid_input
from app.item_schemas import ItemCreate, ItemDetailOut, ItemListOut
from app.items import distance_to, to_item_detail, to_item_out
from app.models import Item, Reservation, User
from app.pricing import split_price
from app.schemas import round_coord

KM_PER_DEGREE = 111.19  # 위도 1도의 거리
ITEM_TYPES = ("GROUP_BUY", "SHARE")
SORTS = ("distance", "deadline")
RADII = (3, 5)

router = APIRouter(prefix="/items", tags=["items"])


@router.post("", status_code=201, response_model=ItemDetailOut)
def create_item(
    body: ItemCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ItemDetailOut:
    # owner_id는 토큰의 사용자로 정한다. 본문에 owner_id가 들어 있어도 무시한다.
    participant_price, _ = split_price(body.total_price, body.total_slots)
    item = Item(
        owner_id=user.id,
        type=body.type,
        category=body.category,
        title=body.title,
        total_slots=body.total_slots,
        total_price=body.total_price,
        price_per_slot=participant_price,
        deadline=body.deadline,
        # 위치를 안 보내면 내 저장 위치(이미 반올림됨), 보내면 서버가 반올림해서 저장한다.
        lat=round_coord(body.lat) if body.lat is not None else user.lat,
        lng=round_coord(body.lng) if body.lng is not None else user.lng,
        pickup_note=body.pickup_note,
        product_url=body.product_url,
        image_url=body.image_url,
    )
    db.add(item)
    db.commit()
    db.refresh(item)  # 서버 기본값(filled_slots, status, created_at)을 읽어 온다
    return to_item_detail(item, owner=user, viewer=user)


def escape_like(text: str) -> str:
    """검색어의 %, _ 가 와일드카드로 동작하지 않게 이스케이프한다."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@router.get("", response_model=ItemListOut)
def list_items(
    type: str,
    sort: str = "distance",
    radius: int = 5,
    q: str | None = Query(default=None, max_length=50),
    lat: float | None = Query(default=None, ge=-90, le=90),
    lng: float | None = Query(default=None, ge=-180, le=180),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ItemListOut:
    """모집 중이고 마감 전인 글만 보여 준다. pickup_note는 응답에 넣지 않는다(ItemOut)."""
    if type not in ITEM_TYPES:
        raise invalid_input("글 유형이 올바르지 않아요", "type")
    if sort not in SORTS:
        raise invalid_input("정렬 방식이 올바르지 않아요", "sort")
    if radius not in RADII:
        raise invalid_input("반경은 3km 또는 5km만 선택할 수 있어요", "radius")
    if (lat is None) != (lng is None):
        raise invalid_input("위도와 경도를 함께 보내 주세요", "lng" if lat is not None else "lat")

    # 거리 기준점: 보낸 좌표(서버가 반올림) 또는 내 저장 위치
    if lat is not None and lng is not None:
        origin = (float(round_coord(lat)), float(round_coord(lng)))
    else:
        origin = (float(user.lat), float(user.lng))

    # DB에서는 대략적인 사각형 범위로 먼저 줄이고, 정확한 거리 계산은 파이썬에서 한다.
    dlat = radius / KM_PER_DEGREE + 0.02
    dlng = radius / (KM_PER_DEGREE * max(cos(radians(origin[0])), 0.01)) + 0.02

    joined = exists().where(Reservation.item_id == Item.id, Reservation.user_id == user.id)
    stmt = (
        select(Item, User, joined)
        .join(User, User.id == Item.owner_id)
        .where(
            Item.type == type,
            Item.status == "OPEN",
            Item.deadline > func.now(),
            Item.lat.between(origin[0] - dlat, origin[0] + dlat),
            Item.lng.between(origin[1] - dlng, origin[1] + dlng),
        )
    )
    keyword = (q or "").strip()
    if keyword:
        stmt = stmt.where(Item.title.ilike(f"%{escape_like(keyword)}%", escape="\\"))

    rows = [
        (item, owner, is_joined, distance_to(item, origin))
        for item, owner, is_joined in db.execute(stmt).all()
    ]
    rows = [row for row in rows if row[3] <= radius]
    if sort == "distance":
        rows.sort(key=lambda r: (r[3], r[0].deadline, r[0].id))
    else:
        rows.sort(key=lambda r: (r[0].deadline, r[0].id))

    return ItemListOut(
        items=[
            to_item_out(item, owner, user, is_joined=is_joined, origin=origin)
            for item, owner, is_joined, _ in rows
        ]
    )
