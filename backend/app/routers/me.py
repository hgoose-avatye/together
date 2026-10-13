from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.item_schemas import (
    KST,
    MyItemListOut,
    ReservationListOut,
    ReservationOut,
    ReservedItemOut,
)
from app.items import display_status, record_failures, to_my_items
from app.models import Item, Reservation, User

router = APIRouter(prefix="/me", tags=["me"])

# shortcut: 페이지 나눔 없음, 한 사람의 신청·글이 수백 건을 넘으면 limit/offset 추가


@router.get("/reservations", response_model=ReservationListOut)
def my_reservations(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ReservationListOut:
    record_failures(db)
    rows = db.execute(
        select(Reservation, Item, User)
        .join(Item, Item.id == Reservation.item_id)
        .join(User, User.id == Item.owner_id)
        .where(Reservation.user_id == user.id)
        .order_by(Reservation.id.desc())
    ).all()

    out = []
    for reservation, item, owner in rows:
        status = display_status(item)
        out.append(
            ReservationOut(
                reservation_id=reservation.id,
                joined_at=reservation.created_at.astimezone(KST),
                item=ReservedItemOut(
                    id=item.id,
                    type=item.type,
                    title=item.title,
                    owner_nickname=owner.nickname,
                    price_per_slot=item.price_per_slot,
                    deadline=item.deadline.astimezone(KST),
                    status=status,
                    pickup_note=item.pickup_note if status == "CONFIRMED" else None,
                    owner_suspended=owner.status == "SUSPENDED",
                ),
            )
        )
    return ReservationListOut(reservations=out)


@router.get("/items", response_model=MyItemListOut)
def my_items(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> MyItemListOut:
    record_failures(db)
    items = db.scalars(
        select(Item).where(Item.owner_id == user.id).order_by(Item.id.desc())
    ).all()

    return MyItemListOut(items=to_my_items(db, items))
