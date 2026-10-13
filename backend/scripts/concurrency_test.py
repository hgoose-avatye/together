"""동시 신청 시연 (기획서 3장 데모 4번, 트러블슈팅 TS-01·02).

실행 중인 서버에 사용자 N명이 같은 순간에 같은 글을 신청하고, 남은 몫만큼만 성공하는지 확인한다.
  1. 몫 신청 경쟁: N명이 동시에 신청 -> 남은 몫 수만큼만 201, 나머지는 SLOTS_FULL
  2. 같은 계정 중복: 한 사람이 동시에 두 번 신청 -> 1건 201, 1건 ALREADY_JOINED

사용법 (서버를 먼저 띄운다: uv run fastapi dev app/main.py)
  cd backend
  uv run python scripts/concurrency_test.py                 # 글을 스스로 만들어서 시연
  uv run python scripts/concurrency_test.py --item 12       # 화면에서 만든 12번 글로 시연
  uv run python scripts/concurrency_test.py --cleanup       # 끝나고 이번에 만든 데이터를 지움(로컬 DB 접근 필요)

화면에서 만든 글로 시연하려면 --lat/--lng를 그 글이 있는 동네로 맞춘다(기본: 망원동).
끝나면 판정 결과에 따라 종료 코드 0(통과) 또는 1(실패)을 돌려준다.
"""

import argparse
import asyncio
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1])
)  # DB 확인용으로 app을 가져온다(없어도 동작)

PASSWORD = "demo-password-1234"


def error_code(r: httpx.Response) -> str | None:
    """실패 응답의 에러 코드. 서버 오류처럼 JSON이 아닌 응답이어도 죽지 않고 HTTP_상태로 보여 준다."""
    if r.status_code < 400:
        return None
    try:
        return r.json().get("code") or f"HTTP_{r.status_code}"
    except ValueError:
        return f"HTTP_{r.status_code}"


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def mark_verified(user_id: int) -> None:
    """시연 계정의 이메일 인증을 DB에서 직접 처리한다. 개발 DB가 아니면 거부한다(기획서 5.11).

    서버가 가리키는 DB와 이 스크립트의 DB가 같아야 한다. 다르면 이후 글 작성·신청이 EMAIL_NOT_VERIFIED로 막힌다.
    """
    from sqlalchemy import text

    from app.db import engine
    from app.dbguard import assert_dev_database

    assert_dev_database(engine)
    with engine.begin() as conn:
        conn.execute(text("UPDATE users SET email_verified_at = now() WHERE id = :i"), {"i": user_id})


async def make_user(
    base: str, email: str, nickname: str, lat: float, lng: float
) -> dict:
    async with httpx.AsyncClient(base_url=base, timeout=60) as c:
        body = {
            "email": email,
            "password": PASSWORD,
            "nickname": nickname,
            "lat": lat,
            "lng": lng,
        }
        r = await c.post("/auth/signup", json=body)
        r.raise_for_status()
        mark_verified(r.json()["id"])
        r = await c.post("/auth/login", json={"email": email, "password": PASSWORD})
        r.raise_for_status()
        return {"token": r.json()["access_token"], "nickname": nickname, "email": email}


async def make_item(
    base: str, owner: dict, title: str, slots: int, lat: float, lng: float
) -> int:
    deadline = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    body = {
        "type": "GROUP_BUY", "title": title, "total_slots": slots, "total_price": 10_000,
        "deadline": deadline, "pickup_note": "시연용 만남 장소", "lat": lat, "lng": lng,
    }  # fmt: skip
    async with httpx.AsyncClient(base_url=base, timeout=60) as c:
        r = await c.post("/items", json=body, headers=auth(owner["token"]))
        r.raise_for_status()
        return r.json()["id"]


async def fire(
    base: str, jobs: list[tuple[str, int]]
) -> list[tuple[int, str | None, float]]:
    """(토큰, 글 id) 목록을 같은 순간에 신청하고 (HTTP 상태, 에러 코드, 걸린 ms)를 돌려준다."""
    clients = [httpx.AsyncClient(base_url=base, timeout=60) for _ in jobs]
    try:
        await asyncio.gather(
            *(c.get("/health") for c in clients)
        )  # 연결을 미리 열어 둔다
        go = asyncio.Event()

        async def one(client: httpx.AsyncClient, token: str, item_id: int):
            await go.wait()
            start = time.perf_counter()
            r = await client.post(f"/items/{item_id}/join", headers=auth(token))
            ms = (time.perf_counter() - start) * 1000
            return r.status_code, error_code(r), ms

        tasks = [asyncio.create_task(one(c, t, i)) for c, (t, i) in zip(clients, jobs)]
        await asyncio.sleep(0.2)  # 모든 요청이 출발선에 선 뒤
        go.set()  # 한꺼번에 출발
        return await asyncio.gather(*tasks)
    finally:
        await asyncio.gather(*(c.aclose() for c in clients))


def db_counts(item_id: int) -> tuple[int, int] | None:
    """(filled_slots, 신청 기록 수). 서버와 같은 DB에 접근할 수 없으면 None."""
    try:
        from sqlalchemy import text

        from app.db import engine

        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT filled_slots, (SELECT count(*) FROM reservations WHERE item_id = i.id) "
                    "FROM items i WHERE id = :id"
                ),
                {"id": item_id},
            ).one()
        return row[0], row[1]
    except Exception:
        return None


def cleanup(prefix: str) -> None:
    try:
        from sqlalchemy import text

        from app.db import engine
        from app.dbguard import UnsafeDatabase, assert_dev_database

        try:
            assert_dev_database(engine)  # 개발 DB가 아니면 지우지 않는다(기획서 5.11)
        except UnsafeDatabase as e:
            print(f"\n정리: 거부했습니다. {e}")
            return

        users = f"SELECT id FROM users WHERE email LIKE '{prefix}%'"
        items = f"SELECT id FROM items WHERE owner_id IN ({users})"
        with engine.begin() as conn:
            conn.execute(
                text(f"DELETE FROM email_verification_tokens WHERE user_id IN ({users})")
            )
            conn.execute(
                text(f"DELETE FROM admin_actions WHERE target_user_id IN ({users})")
            )
            conn.execute(
                text(
                    f"DELETE FROM reports WHERE reporter_id IN ({users}) "
                    f"OR target_user_id IN ({users}) OR item_id IN ({items})"
                )
            )
            conn.execute(
                text(
                    f"DELETE FROM reservations WHERE user_id IN ({users}) OR item_id IN ({items})"
                )
            )
            conn.execute(text(f"DELETE FROM items WHERE owner_id IN ({users})"))
            conn.execute(text(f"DELETE FROM users WHERE email LIKE '{prefix}%'"))
        print("\n정리: 이번에 만든 시연 데이터를 지웠습니다.")
    except Exception:
        print(
            "\n정리: 서버와 같은 DB에 접근할 수 없어 건너뜁니다(이메일이 demo-로 시작하는 계정이 남습니다)."
        )


def show(results, names) -> None:
    for name, (status, code, ms) in zip(names, results):  # 한글은 두 칸이라 사유를 맨 끝에 둬서 정렬이 깨지지 않게 한다
        print(f"   {name:<8} {ms:5.0f}ms  {status}  {'성공' if status == 201 else code}")


async def race(base, args, run_id) -> bool:
    print(f"\n[1] 몫 신청 경쟁: {args.users}명이 같은 순간에 같은 글을 신청합니다")
    owner = None
    if args.item:
        item_id = args.item
    else:
        owner = await make_user(
            base, f"demo-{run_id}-owner@example.com", "개설자", args.lat, args.lng
        )
        item_id = await make_item(
            base, owner, f"동시 신청 시연 {run_id}", 1, args.lat, args.lng
        )
    users = await asyncio.gather(*(
        make_user(base, f"demo-{run_id}-u{n}@example.com", f"참여자{n}", args.lat, args.lng)
        for n in range(1, args.users + 1)
    ))  # fmt: skip

    async with httpx.AsyncClient(base_url=base, timeout=60) as c:
        listed = (await c.get("/items", params={"type": "GROUP_BUY", "lat": args.lat, "lng": args.lng},
                              headers=auth(users[0]["token"]))).json()["items"]  # fmt: skip
    found = next((i for i in listed if i["id"] == item_id), None)
    if found is None:
        print(
            f"   글 #{item_id}을 찾지 못했습니다. 모집 중인 글인지, --lat/--lng가 글이 있는 동네(반경 5km)인지 확인하세요."
        )
        return False
    remaining = found["remaining_slots"]
    expected = min(args.users, remaining)
    print(
        f'   대상: 글 #{item_id} "{found["title"]}" (남은 몫 {remaining}개) -> 성공은 정확히 {expected}건이어야 합니다'
    )

    results = await fire(base, [(u["token"], item_id) for u in users])
    show(results, [u["nickname"] for u in users])

    ok_count = sum(1 for s, _, _ in results if s == 201)
    others = [c for s, c, _ in results if s != 201]
    server_errors = [s for s, _, _ in results if s >= 500]

    # 사용자 쪽에서 본 결과: 내 참여에 이 글이 몇 건 생겼는가
    async def reservations_of(u):
        async with httpx.AsyncClient(base_url=base, timeout=60) as c:
            rows = (await c.get("/me/reservations", headers=auth(u["token"]))).json()[
                "reservations"
            ]
        return [r["item"]["status"] for r in rows if r["item"]["id"] == item_id]

    seen = [
        s
        for st in await asyncio.gather(*(reservations_of(u) for u in users))
        for s in st
    ]
    counts = db_counts(item_id)

    print("\n   결과")
    print(
        f"   - 성공 {ok_count}건 / SLOTS_FULL {others.count('SLOTS_FULL')}건 / 그 밖 {len(others) - others.count('SLOTS_FULL')}건 / 서버 오류 {len(server_errors)}건"
    )
    print(
        f"   - 참여자들의 내 참여에 이 글이 생긴 수: {len(seen)}건 (글 상태: {sorted(set(seen)) or '없음'})"
    )
    checks = [
        (ok_count == expected, f"성공이 정확히 {expected}건"),
        (set(others) <= {"SLOTS_FULL"}, "실패는 모두 SLOTS_FULL"),
        (not server_errors, "서버 오류(5xx) 없음"),
        (len(seen) == ok_count, "신청 기록 수 = 성공 수"),
    ]
    if counts:
        print(f"   - DB: filled_slots={counts[0]}, 신청 기록={counts[1]}")
        checks.append(
            (counts[0] == counts[1] == ok_count, "filled_slots = 신청 기록 수")
        )
    else:
        print("   - DB: 직접 확인 생략(서버와 같은 DB에 접근할 수 없음)")
    if remaining == expected:
        checks.append(
            (set(seen) == {"CONFIRMED"}, "마지막 몫이 차서 글이 성사(CONFIRMED)")
        )
    return report(checks)


async def same_account(base, args, run_id) -> bool:
    print("\n[2] 같은 계정 중복: 한 사람이 같은 순간에 두 번 신청합니다")
    owner = await make_user(
        base, f"demo-{run_id}-owner2@example.com", "개설자2", args.lat, args.lng
    )
    me = await make_user(
        base, f"demo-{run_id}-me@example.com", "중복신청자", args.lat, args.lng
    )
    item_id = await make_item(
        base, owner, f"중복 신청 시연 {run_id}", 1, args.lat, args.lng
    )

    results = await fire(base, [(me["token"], item_id)] * 2)
    show(results, ["요청 1", "요청 2"])
    codes = sorted(str(c) for _, c, _ in results)
    counts = db_counts(item_id)
    checks = [
        (sorted(s for s, _, _ in results) == [201, 409], "1건 성공, 1건 409"),
        (
            codes == ["ALREADY_JOINED", "None"],
            "실패 사유는 ALREADY_JOINED (SLOTS_FULL 아님)",
        ),
    ]
    if counts:
        print(f"   - DB: filled_slots={counts[0]}, 신청 기록={counts[1]}")
        checks.append((counts[0] == counts[1] == 1, "몫이 한 번만 늘었다"))
    return report(checks)


def report(checks: list[tuple[bool, str]]) -> bool:
    print()
    for ok, label in checks:
        print(f"   {'✓' if ok else '✗'} {label}")
    return all(ok for ok, _ in checks)


async def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--base-url", default="http://localhost:8000")
    ap.add_argument(
        "--users", type=int, default=10, help="동시에 신청할 사람 수 (기본 10)"
    )
    ap.add_argument("--item", type=int, help="이 글 id로 시연 (없으면 스스로 만든다)")
    ap.add_argument(
        "--lat", type=float, default=37.56, help="시연 사용자 위치 (기본: 망원동)"
    )
    ap.add_argument("--lng", type=float, default=126.90)
    ap.add_argument("--skip-same-account", action="store_true")
    ap.add_argument(
        "--cleanup", action="store_true", help="끝나고 이번에 만든 데이터를 지운다"
    )
    args = ap.parse_args()
    run_id, base = int(time.time()), args.base_url.rstrip("/")

    print(f"같이 동시 신청 시연  (서버: {base})")
    try:
        print("준비: 사용자 가입·로그인 중...")
        passed = [await race(base, args, run_id)]
        if not args.skip_same_account:
            passed.append(await same_account(base, args, run_id))
        verdict = "통과 ✓  남은 몫만큼만 성공하고, 중복은 막혔습니다." if all(passed) else "실패 ✗  위의 ✗ 항목을 확인하세요."
        print("\n판정:", verdict)
        return 0 if all(passed) else 1
    except httpx.HTTPError as e:
        print(f"\n서버에 요청하지 못했습니다: {e}\n서버가 떠 있는지(uv run fastapi dev app/main.py), --base-url이 맞는지 확인하세요.")
        return 2
    finally:  # 중간에 어떤 이유로 끝나도 이번에 만든 데이터는 지운다
        if args.cleanup:
            cleanup(f"demo-{run_id}-")


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
