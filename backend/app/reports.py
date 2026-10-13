"""A-10 신고 (기획서 5.9). 접수만 하고 자동으로 제재하지 않는다.

신고 대상은 클라이언트가 보내지 않고 서버가 글과 신청 기록으로 정한다.
"""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import AppError, invalid_input
from app.item_schemas import ReportCreate
from app.join import MAX_BIGINT, UNIQUE_VIOLATION
from app.models import Item, Report, Reservation, User


def create_report(db: Session, reporter: User, body: ReportCreate) -> Report:
    if not 1 <= body.item_id <= MAX_BIGINT:
        raise AppError("NOT_FOUND")
    item = db.get(Item, body.item_id)
    if item is None:
        raise AppError("NOT_FOUND")

    if body.reservation_id is None:
        # 글 개설자를 신고한다. 관계없는 사용자도 할 수 있다(남용 가능성은 알려진 한계, 5.9).
        if item.owner_id == reporter.id:
            raise invalid_input("내가 올린 글은 신고할 수 없어요", "item_id")
        target_id = item.owner_id
    else:
        # 참여자를 신고한다. 개설자만 할 수 있고, 권한을 먼저 확인해 남이 신청 기록의 존재를 알아내지 못하게 한다.
        if item.owner_id != reporter.id:
            raise AppError("NOT_OWNER", "내가 올린 글의 참여자만 신고할 수 있어요")
        if not 1 <= body.reservation_id <= MAX_BIGINT:
            raise AppError("NOT_FOUND", "신청을 찾을 수 없어요")
        reservation = db.get(Reservation, body.reservation_id)
        if reservation is None or reservation.item_id != item.id:
            raise AppError("NOT_FOUND", "신청을 찾을 수 없어요")
        target_id = reservation.user_id

    report = Report(
        reporter_id=reporter.id,
        target_user_id=target_id,
        item_id=item.id,
        reason=body.reason,
        detail=body.detail,
    )
    db.add(report)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        if getattr(e.orig, "sqlstate", None) == UNIQUE_VIOLATION:
            raise AppError("ALREADY_REPORTED") from e
        raise
    return report
