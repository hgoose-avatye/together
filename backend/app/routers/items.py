from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.item_schemas import ItemCreate, ItemDetailOut
from app.items import to_item_detail
from app.models import Item, User
from app.pricing import split_price
from app.schemas import round_coord

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
