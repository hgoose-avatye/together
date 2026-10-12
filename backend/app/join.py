"""A-05 몫 신청 (기획서 9.5). 이 서비스의 핵심이자 발표 포인트.

몫 증가와 성사 전환은 아래 조건부 UPDATE **한 문장**으로 처리한다.
PostgreSQL은 같은 행을 UPDATE하려는 트랜잭션을 줄 세우고, 먼저 커밋된 쪽이 있으면
뒤 요청은 바뀐 행으로 WHERE를 다시 평가한다. 그래서 `filled_slots < total_slots`가
거짓이 되어 0행이 되고, 별도의 행 잠금(SELECT ... FOR UPDATE)이 필요 없다.
"""

from typing import NamedTuple

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import AppError
from app.item_schemas import JoinOut

MAX_BIGINT = 2**63 - 1
UNIQUE_VIOLATION = "23505"

# 몫 증가 + 마지막 몫이면 성사 전환 + 결과 읽기가 한 문장에서 일어난다.
JOIN_SQL = text(
    """
    UPDATE items
    SET filled_slots = filled_slots + 1,
        status = CASE WHEN filled_slots + 1 = total_slots
                      THEN 'CONFIRMED' ELSE status END
    WHERE id = :item_id
      AND status = 'OPEN'
      AND deadline > now()
      AND filled_slots < total_slots
      AND owner_id <> :user_id
    RETURNING filled_slots, total_slots, status
    """
)

INSERT_RESERVATION_SQL = text(
    "INSERT INTO reservations (item_id, user_id) VALUES (:item_id, :user_id) RETURNING id"
)

# UPDATE가 0행일 때 이유를 가리기 위한 조회. 한 문장이라 같은 시점의 값으로 판단한다.
CAUSE_SQL = text(
    """
    SELECT i.owner_id, i.status, (i.deadline <= now()) AS past_deadline,
           EXISTS (SELECT 1 FROM reservations r
                   WHERE r.item_id = i.id AND r.user_id = :user_id) AS joined
    FROM items i
    WHERE i.id = :item_id
    """
)


class Cause(NamedTuple):
    owner_id: int
    status: str
    past_deadline: bool
    joined: bool


def classify_failure(cause: Cause | None, user_id: int) -> str:
    """신청이 안 된 이유를 정해진 순서로 판정해 에러 코드를 돌려준다(기획서 9.5 3단계).

    글 없음 -> 이미 신청함 -> 내 글 -> 마감·무산·취소 -> 몫 소진.
    "이미 신청함"을 앞에 두는 이유: 같은 계정이 마지막 몫에 동시에 두 번 신청하면
    두 번째 요청은 UPDATE가 0행이지만, 사용자에게는 "이미 신청함"이 정확한 안내이기 때문이다.
    """
    if cause is None:
        return "NOT_FOUND"
    if cause.joined:
        return "ALREADY_JOINED"
    if cause.owner_id == user_id:
        return "OWN_ITEM"
    if cause.status in ("FAILED", "CANCELED") or cause.past_deadline:
        return "EXPIRED"
    return "SLOTS_FULL"


def join_item(db: Session, item_id: int, user_id: int) -> JoinOut:
    if (
        not 1 <= item_id <= MAX_BIGINT
    ):  # bigint 범위를 벗어난 id는 DB에 보내지 않고 없는 글로 본다
        raise AppError("NOT_FOUND")
    params = {"item_id": item_id, "user_id": user_id}

    # 1. 조건부 UPDATE (트랜잭션은 이 문장에서 자동으로 시작된다)
    updated = db.execute(JOIN_SQL, params).first()

    if updated is None:
        # 2. 0행: 롤백하고 이유를 가린다.
        db.rollback()
        cause = db.execute(CAUSE_SQL, params).first()
        db.rollback()
        raise AppError(classify_failure(Cause(*cause) if cause else None, user_id))

    # 3. 1행: 신청 기록을 넣는다. 같은 사람이 다시 신청하면 UNIQUE 위반이 나고,
    #    트랜잭션 전체를 되돌려 위 UPDATE의 filled_slots 증가도 함께 취소한다.
    try:
        reservation_id = db.execute(INSERT_RESERVATION_SQL, params).scalar_one()
    except IntegrityError as e:
        db.rollback()
        if getattr(e.orig, "sqlstate", None) == UNIQUE_VIOLATION:
            raise AppError("ALREADY_JOINED") from e
        raise

    db.commit()
    return JoinOut(
        reservation_id=reservation_id,
        item_id=item_id,
        filled_slots=updated.filled_slots,
        total_slots=updated.total_slots,
        remaining_slots=updated.total_slots - updated.filled_slots,
        status=updated.status,
    )
