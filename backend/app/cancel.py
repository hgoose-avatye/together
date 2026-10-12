"""A-09 개설 취소 (기획서 9.7). 신청(A-05)과 같은 방식의 조건부 UPDATE 한 문장이다.

같은 행을 두고 신청과 취소가 동시에 와도 한쪽만 통과한다. 취소가 먼저면 신청은 `status = 'OPEN'`에서
막히고(EXPIRED), 마지막 몫이 먼저 차서 CONFIRMED가 되면 취소가 막힌다(NOT_OPEN).
"""

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.errors import AppError
from app.item_schemas import MyItemOut
from app.items import to_my_items
from app.join import MAX_BIGINT
from app.models import Item

CANCEL_SQL = text(
    """
    UPDATE items SET status = 'CANCELED'
    WHERE id = :item_id
      AND owner_id = :user_id
      AND status = 'OPEN'
      AND deadline > now()
    RETURNING id
    """
)

OWNER_SQL = text("SELECT owner_id FROM items WHERE id = :item_id")


def cancel_item(db: Session, item_id: int, user_id: int) -> MyItemOut:
    if not 1 <= item_id <= MAX_BIGINT:
        raise AppError("NOT_FOUND")
    params = {"item_id": item_id, "user_id": user_id}

    if db.execute(CANCEL_SQL, params).first() is None:
        # 0행: 글 없음 -> 남의 글 -> 그 밖(성사·무산·취소·마감)
        db.rollback()
        owner_id = db.execute(OWNER_SQL, params).scalar()
        db.rollback()
        if owner_id is None:
            raise AppError("NOT_FOUND")
        raise AppError("NOT_OWNER" if owner_id != user_id else "NOT_OPEN")

    db.commit()
    return to_my_items(db, [db.get(Item, item_id)])[0]
