"""계정 정지·해제와 관리 감사 기록 (기획서 5.9). admin.py가 쓴다. 사용자용 API에서는 부르지 않는다."""

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.models import AdminAction, Report, User

# 개설 취소(9.7)와 같은 조건부 UPDATE. 같은 행의 신청(A-05)과 동시에 와도 한쪽만 통과한다:
# 정지가 먼저면 글이 취소되고 신청은 EXPIRED, 신청이 먼저 마지막 몫을 채우면 CONFIRMED로 남아 여기서 건너뛴다.
CANCEL_OPEN_ITEMS_SQL = text(
    "UPDATE items SET status = 'CANCELED' "
    "WHERE owner_id = :user_id AND status = 'OPEN' RETURNING id"
)


class AdminError(Exception):
    pass


def _log(db: Session, action: str, user_id: int, os_user: str, note: str | None, report_id: int | None = None):
    db.add(
        AdminAction(
            action=action,
            target_user_id=user_id,
            report_id=report_id,
            actor_os_user=os_user,
            note=note,
        )
    )


def _suspend(db: Session, user: User, reason: str, os_user: str, report_id: int | None) -> list[int]:
    user.status = "SUSPENDED"
    user.suspended_at = func.now()
    user.suspension_reason = reason
    db.flush()
    canceled = [r[0] for r in db.execute(CANCEL_OPEN_ITEMS_SQL, {"user_id": user.id})]
    _log(db, "SUSPEND", user.id, os_user, reason, report_id)
    return canceled


def suspend_user(
    db: Session, user_id: int, reason: str, os_user: str, report_id: int | None = None
) -> list[int]:
    """계정을 정지하고 모집 중인 글을 취소한다. 취소한 글 id를 돌려준다. 한 트랜잭션이다."""
    user = db.get(User, user_id, with_for_update=True)  # 같은 사용자의 동시 정지·해제를 줄이려고 행을 잠근다
    if user is None:
        raise AdminError(f"사용자 {user_id}가 없습니다")
    if user.status == "SUSPENDED":
        raise AdminError(f"사용자 {user_id}는 이미 정지 상태입니다")
    canceled = _suspend(db, user, reason, os_user, report_id)
    db.commit()
    return canceled


def unsuspend_user(db: Session, user_id: int, note: str, os_user: str) -> None:
    """정지를 풀어 준다. 취소된 글은 복구하지 않는다."""
    user = db.get(User, user_id, with_for_update=True)
    if user is None:
        raise AdminError(f"사용자 {user_id}가 없습니다")
    if user.status != "SUSPENDED":
        raise AdminError(f"사용자 {user_id}는 정지 상태가 아닙니다")
    user.status = "ACTIVE"
    user.suspended_at = None
    user.suspension_reason = None
    _log(db, "UNSUSPEND", user_id, os_user, note)
    db.commit()


def resolve_report(
    db: Session, report_id: int, resolution: str, note: str, os_user: str
) -> list[int]:
    """신고를 처리한다. SUSPENDED이면 대상 계정 정지(모집 중 글 취소)까지 한 트랜잭션에서 한다.

    정지되어 있던 대상이면 정지는 건너뛰고 신고만 처리한다. 취소한 글 id를 돌려준다.
    """
    if resolution not in ("DISMISSED", "SUSPENDED"):
        raise AdminError("처리 결과는 DISMISSED 또는 SUSPENDED여야 합니다")
    report = db.get(Report, report_id, with_for_update=True)
    if report is None:
        raise AdminError(f"신고 {report_id}가 없습니다")
    if report.status != "OPEN":
        raise AdminError(f"신고 {report_id}는 이미 처리됐습니다")
    canceled: list[int] = []
    if resolution == "SUSPENDED":
        target = db.get(User, report.target_user_id, with_for_update=True)
        if target.status != "SUSPENDED":
            canceled = _suspend(db, target, note, os_user, report.id)
    report.status = "RESOLVED"
    report.resolution = resolution
    report.resolved_at = func.now()
    report.resolution_note = note
    _log(db, "RESOLVE_REPORT", report.target_user_id, os_user, f"{resolution}: {note}", report.id)
    db.commit()
    return canceled
