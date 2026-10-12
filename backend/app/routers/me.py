from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.item_schemas import (
    KST,
    MyItemListOut,
    MyItemOut,
    ParticipantOut,
    ReservationListOut,
    ReservationOut,
    ReservedItemOut,
)
from app.items import display_status, record_failures
from app.models import Item, Reservation, User
from app.pricing import split_price

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

    participants = defaultdict(list)  # 글마다 따로 조회하지 않고 한 번에 가져온다
    if items:
        for item_id, joined_at, nickname in db.execute(
            select(Reservation.item_id, Reservation.created_at, User.nickname)
            .join(User, User.id == Reservation.user_id)
            .where(Reservation.item_id.in_([i.id for i in items]))
            .order_by(Reservation.id)
        ):
            participants[item_id].append(
                ParticipantOut(nickname=nickname, joined_at=joined_at.astimezone(KST))
            )

    return MyItemListOut(
        items=[
            MyItemOut(
                id=i.id,
                type=i.type,
                title=i.title,
                filled_slots=i.filled_slots,
                total_slots=i.total_slots,
                total_price=i.total_price,
                price_per_slot=i.price_per_slot,
                owner_share=split_price(i.total_price, i.total_slots)[1],
                deadline=i.deadline.astimezone(KST),
                status=display_status(i),
                pickup_note=i.pickup_note,  # 개설자 본인에게는 항상 보인다
                participants=participants[i.id],
            )
            for i in items
        ]
    )
