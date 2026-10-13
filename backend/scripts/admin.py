"""운영 도구: 신고 처리와 계정 정지·해제 (기획서 5.11).

운영 DB에서 쓰는 것이 목적이라 개발 DB 보호 검사(dbguard)를 적용하지 않는다. 대신:
  - 실행할 때 대상 DB(프로젝트 id)를 화면에 보여 준다.
  - 변경 명령은 --yes가 없으면 아무것도 바꾸지 않고 무엇을 할지만 보여 준다.
  - 모든 변경은 admin_actions에 남긴다. 기록의 실행자는 OS 사용자 이름일 뿐 관리자 개인 인증이 아니다.

사용법 (cd backend)
  uv run python scripts/admin.py reports [--all]
  uv run python scripts/admin.py show <신고 id>
  uv run python scripts/admin.py resolve <신고 id> --dismiss|--suspend --note "메모" [--yes]
  uv run python scripts/admin.py ban <사용자 id> --note "사유" [--yes]
  uv run python scripts/admin.py unban <사용자 id> --note "메모" [--yes]
"""

import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.db import engine  # noqa: E402
from app.dbguard import project_id  # noqa: E402
from app.models import Item, Report, User  # noqa: E402
from app.suspension import AdminError, resolve_report, suspend_user, unsuspend_user  # noqa: E402


def describe(user: User) -> str:
    return f"#{user.id} {user.nickname} <{user.email}> [{user.status}]"


def cmd_reports(db: Session, args) -> None:
    q = select(Report).order_by(Report.id)
    if not args.all:
        q = q.where(Report.status == "OPEN")
    rows = db.scalars(q).all()
    for r in rows:
        print(f"신고 #{r.id} {r.status} {r.reason} 글#{r.item_id} 신고자#{r.reporter_id} -> 대상#{r.target_user_id}  {r.created_at:%Y-%m-%d %H:%M}")
    print(f"{len(rows)}건")


def cmd_show(db: Session, args) -> None:
    r = db.get(Report, args.id)
    if r is None:
        sys.exit(f"신고 {args.id}가 없습니다")
    item = db.get(Item, r.item_id)
    print(f"신고 #{r.id}  상태 {r.status}  결과 {r.resolution}  사유 {r.reason}")
    print(f"설명: {r.detail or '(없음)'}")
    print(f"신고자: {describe(db.get(User, r.reporter_id))}")
    print(f"대상:   {describe(db.get(User, r.target_user_id))}")
    print(f"글: #{item.id} {item.title} [{item.status}]")
    if r.resolved_at:
        print(f"처리: {r.resolved_at:%Y-%m-%d %H:%M} {r.resolution_note}")


def confirm(args, what: str) -> bool:
    print(f"할 일: {what}")
    if not args.yes:
        print("--yes가 없어 아무것도 바꾸지 않았습니다.")
        return False
    return True


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("reports"); p.add_argument("--all", action="store_true")  # noqa: E702
    p = sub.add_parser("show"); p.add_argument("id", type=int)  # noqa: E702
    p = sub.add_parser("resolve"); p.add_argument("id", type=int)  # noqa: E702
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--dismiss", action="store_true")
    g.add_argument("--suspend", action="store_true")
    for name in ("resolve", "ban", "unban"):
        q = sub.choices[name] if name in sub.choices else sub.add_parser(name)
        if name != "resolve":
            q.add_argument("id", type=int)
        q.add_argument("--note", required=True)
        q.add_argument("--yes", action="store_true")
    args = ap.parse_args()

    print(f"대상 DB 프로젝트: {project_id(engine.url) or '(알 수 없음)'}")
    os_user = getpass.getuser()
    with Session(engine) as db:
        try:
            if args.cmd == "reports":
                cmd_reports(db, args)
            elif args.cmd == "show":
                cmd_show(db, args)
            elif args.cmd == "resolve":
                r = db.get(Report, args.id)
                if r is None:
                    sys.exit(f"신고 {args.id}가 없습니다")
                res = "SUSPENDED" if args.suspend else "DISMISSED"
                target = db.get(User, r.target_user_id)
                if confirm(args, f"신고 #{r.id}를 {res}로 처리 (대상 {describe(target)}, 실행자 {os_user})"):
                    canceled = resolve_report(db, r.id, res, args.note, os_user)
                    print(f"처리했습니다. 취소된 모집 글: {canceled}")
            elif args.cmd in ("ban", "unban"):
                user = db.get(User, args.id)
                if user is None:
                    sys.exit(f"사용자 {args.id}가 없습니다")
                verb = "정지" if args.cmd == "ban" else "해제"
                if confirm(args, f"{describe(user)} 계정 {verb} (실행자 {os_user})"):
                    if args.cmd == "ban":
                        print(f"정지했습니다. 취소된 모집 글: {suspend_user(db, user.id, args.note, os_user)}")
                    else:
                        unsuspend_user(db, user.id, args.note, os_user)
                        print("해제했습니다. 취소된 글은 복구되지 않습니다.")
        except AdminError as e:
            sys.exit(f"실패: {e}")


if __name__ == "__main__":
    main()
