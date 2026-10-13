from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.item_schemas import ReportCreate, ReportOut
from app.models import User
from app.reports import create_report

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("", status_code=201, response_model=ReportOut)
def report(
    body: ReportCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReportOut:
    """신고를 접수한다. 신고자는 토큰으로 정하고, 대상은 서버가 정한다."""
    r = create_report(db, user, body)
    return ReportOut(id=r.id, status=r.status)
