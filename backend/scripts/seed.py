"""시드 데이터: 데모 화면을 채우고 목록 성능(1,000건)을 확인하는 데이터를 개발 DB에 넣는다 (기획서 13장).

  cd backend
  uv run python scripts/seed.py                 # 지우고 새로 넣기(기본 글 1,000건)
  uv run python scripts/seed.py --count 300     # 건수 바꾸기
  uv run python scripts/seed.py --clean         # 시드·데모 데이터만 지우기

- 이메일이 `seed-`로 시작하는 계정(가상 이웃)과 `demo-`로 시작하는 계정(시연용)만 만들고 지운다.
- 시연 계정: demo-owner@example.com(망원동), demo-guest@example.com(합정동). 비밀번호는 아래 DEMO_PASSWORD.
- 사진은 직접 만든 단색 그림 6장을 Storage에 올려 쓴다(사진 업로드 기능을 대신하지 않는다, 기획서 3장).
- 개발 DB에서만 돈다(기획서 5.11). 운영 DB 시연 데이터는 API 경로로 따로 만든다(배포 단계).
- 같은 입력이면 같은 데이터가 나온다(난수 씨앗 고정). 마감 시각은 실행 시점 기준이라 다시 실행하면 갱신된다.
"""

import argparse
import random
import struct
import sys
import time
import uuid
import zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import insert, text  # noqa: E402

from app.config import settings  # noqa: E402
from app.db import engine  # noqa: E402
from app.dbguard import UnsafeDatabase, assert_dev_database  # noqa: E402
from app.models import Item, Reservation, User  # noqa: E402
from app.pricing import split_price  # noqa: E402
from app.security import hash_password  # noqa: E402

DEMO_PASSWORD = "demo-password-1234"
KST = timezone(timedelta(hours=9))

# 프론트의 동네 목록(frontend/src/neighborhoods.ts)과 같다
HOODS = [
    ("망원동", 37.56, 126.90), ("합정동", 37.55, 126.91), ("연남동", 37.56, 126.93),
    ("홍대입구", 37.56, 126.92), ("신촌", 37.56, 126.94), ("공덕", 37.54, 126.95),
    ("여의도", 37.52, 126.92), ("영등포", 37.52, 126.91), ("노량진", 37.51, 126.94),
    ("신림", 37.48, 126.93), ("사당", 37.48, 126.98), ("이태원", 37.53, 126.99),
    ("혜화", 37.58, 127.00), ("왕십리", 37.56, 127.04), ("성수동", 37.54, 127.06),
    ("건대입구", 37.54, 127.07), ("잠실", 37.51, 127.10), ("강남역", 37.50, 127.03),
    ("서초동", 37.48, 127.03), ("노원", 37.66, 127.06),
]  # fmt: skip

# (제목, 분류, 총액 범위)
PRODUCTS = [
    ("샤인머스켓 2kg 같이 사요", "FRUIT_VEG", (22000, 32000)), ("감귤 10kg 한 박스", "FRUIT_VEG", (18000, 28000)),
    ("대파 5kg 큰 단", "FRUIT_VEG", (9000, 15000)), ("양파 15kg 망", "FRUIT_VEG", (14000, 22000)),
    ("방울토마토 5kg", "FRUIT_VEG", (16000, 24000)), ("고구마 10kg 박스", "FRUIT_VEG", (20000, 30000)),
    ("냉동 닭가슴살 10kg", "FOOD", (45000, 60000)), ("즉석밥 24개입", "FOOD", (22000, 30000)),
    ("신라면 40봉 박스", "FOOD", (26000, 34000)), ("올리브유 2L", "FOOD", (18000, 28000)),
    ("냉동 만두 2.4kg 대용량", "FOOD", (14000, 20000)), ("원두 1kg 두 봉지", "FOOD", (30000, 42000)),
    ("휴지 30롤 두 팩", "HOUSEHOLD", (24000, 34000)), ("세탁세제 5L 대용량", "HOUSEHOLD", (15000, 22000)),
    ("주방세제 리필 3L", "HOUSEHOLD", (9000, 14000)), ("지퍼백 대용량 세트", "HOUSEHOLD", (11000, 17000)),
    ("일회용 마스크 100매", "ETC", (12000, 18000)), ("건전지 AA 40개입", "ETC", (17000, 26000)),
]  # fmt: skip
SHARE_TITLES = [
    "두부 반 모, 내일까지", "남은 대파 한 단", "우유 500ml 두 팩", "양상추 한 통", "계란 6구",
    "식빵 반 봉지", "방울토마토 한 팩", "샐러드 채소 반 봉지", "요거트 4개", "당근 3개",
]  # fmt: skip
NICKS = ["라면왕", "자취생", "야식러", "장보기고수", "알뜰이", "냉장고요정", "절약왕", "새벽배송", "동네친구", "혼밥러", "살림꾼", "먹보", "깔끔이", "든든이", "소소한"]
NOTES = ["{hood} 역 앞, 평일 저녁 7시 이후, 오픈채팅 https://open.kakao.com/o/seed", "{hood} 편의점 앞, 토요일 오후 2시, 오픈채팅 링크는 성사 후", "{hood} 공원 입구, 오늘 21시, 오픈채팅"]  # fmt: skip


def png(width: int, height: int, rgb: tuple[int, int, int]) -> bytes:
    """외부 라이브러리 없이 만드는 세로 줄무늬 PNG."""
    rows = bytearray()
    for _ in range(height):
        rows.append(0)
        for x in range(width):
            k = 1.0 - 0.35 * ((x // 24) % 2)
            rows += bytes(int(c * k) for c in rgb)

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(bytes(rows), 9)) + chunk(b"IEND", b"")


COLORS = [(231, 111, 81), (244, 162, 97), (233, 196, 106), (42, 157, 143), (38, 70, 83), (142, 202, 230)]


def upload_images() -> list[str]:
    """색이 다른 그림 6장을 올리고 공개 주소를 돌려준다. 이름이 고정이라 다시 실행해도 같은 파일을 덮어쓴다."""
    base = f"{settings.supabase_url.rstrip('/')}/storage/v1/object"
    headers = {"apikey": settings.supabase_service_key, "Authorization": f"Bearer {settings.supabase_service_key}", "Content-Type": "image/png", "x-upsert": "true"}  # fmt: skip
    urls = []
    for i, rgb in enumerate(COLORS):
        name = f"{uuid.uuid5(uuid.NAMESPACE_URL, f'gachi-seed-{i}')}.png"
        r = httpx.post(f"{base}/{settings.supabase_bucket}/{name}", content=png(320, 240, rgb), headers=headers, timeout=20)
        if r.status_code not in (200, 201):
            sys.exit(f"사진 올리기 실패({r.status_code}): {r.text[:200]}")
        urls.append(f"{base}/public/{settings.supabase_bucket}/{name}")
    return urls


def clean(conn) -> None:
    users = "SELECT id FROM users WHERE email LIKE 'seed-%' OR email LIKE 'demo-%'"
    items = f"SELECT id FROM items WHERE owner_id IN ({users})"
    conn.execute(text(f"DELETE FROM email_verification_tokens WHERE user_id IN ({users})"))
    conn.execute(text(f"DELETE FROM admin_actions WHERE target_user_id IN ({users})"))
    conn.execute(text(f"DELETE FROM reports WHERE reporter_id IN ({users}) OR target_user_id IN ({users}) OR item_id IN ({items})"))
    conn.execute(text(f"DELETE FROM reservations WHERE user_id IN ({users}) OR item_id IN ({items})"))
    conn.execute(text(f"DELETE FROM items WHERE owner_id IN ({users})"))
    conn.execute(text("DELETE FROM users WHERE email LIKE 'seed-%' OR email LIKE 'demo-%'"))


def jitter(rng: random.Random, lat: float, lng: float) -> tuple[float, float]:
    return round(lat + rng.uniform(-0.015, 0.015), 2), round(lng + rng.uniform(-0.015, 0.015), 2)


def build(count: int, images: list[str]) -> None:
    rng = random.Random(42)
    now = datetime.now(timezone.utc)
    seed_hash = hash_password("seed-not-for-login")  # 시드 이웃은 로그인하지 않는다
    demo_hash = hash_password(DEMO_PASSWORD)

    with engine.begin() as conn:
        clean(conn)

        # ---- 사용자 ----
        users = []
        for n in range(60):
            hood = HOODS[n % len(HOODS)]
            lat, lng = jitter(rng, hood[1], hood[2])
            users.append(dict(email=f"seed-{n:03d}@example.com", password_hash=seed_hash, nickname=f"{hood[0]}{rng.choice(NICKS)}"[:20], lat=lat, lng=lng, email_verified_at=now))  # fmt: skip
        for email, nick, hood in (("demo-owner@example.com", "시연개설자", HOODS[0]), ("demo-guest@example.com", "시연참여자", HOODS[1])):
            users.append(dict(email=email, password_hash=demo_hash, nickname=nick, lat=hood[1], lng=hood[2], email_verified_at=now))  # fmt: skip
        ids = [r[0] for r in conn.execute(insert(User.__table__).returning(User.id, sort_by_parameter_order=True), users)]
        seed_ids = ids[:60]
        owner_id, guest_id = ids[60], ids[61]
        home = {uid: (u["lat"], u["lng"]) for uid, u in zip(ids, users)}

        # ---- 글 ----
        items, fills = [], []  # fills[i] = 신청자로 채울 사용자 id 목록
        def add(owner, title, category, type_, slots, price, deadline, status, filled, lat, lng, image):
            part, _ = split_price(price, slots)
            hood = min(HOODS, key=lambda h: (h[1] - lat) ** 2 + (h[2] - lng) ** 2)[0]
            items.append(dict(owner_id=owner, type=type_, category=category, title=title, total_slots=slots, total_price=price, price_per_slot=part, filled_slots=len(filled), deadline=deadline, lat=lat, lng=lng, pickup_note=rng.choice(NOTES).format(hood=hood), image_url=image, status=status))  # fmt: skip
            fills.append(filled)

        def others(owner, k):
            pool = [u for u in seed_ids if u != owner]
            return rng.sample(pool, k)

        for _ in range(count):
            owner = rng.choice(seed_ids)
            lat, lng = jitter(rng, *home[owner])
            roll = rng.random()
            if roll < 0.10:  # 나눔: 사진 필수, 1몫, 0원, 유통기한 다음 날 00:00
                expiry = (now.astimezone(KST) + timedelta(days=rng.randint(0, 4))).date()
                deadline = datetime.combine(expiry + timedelta(days=1), datetime.min.time(), KST)
                add(owner, rng.choice(SHARE_TITLES), "ETC", "SHARE", 1, 0, deadline, "OPEN", [], lat, lng, rng.choice(images))
                continue
            title, category, (lo, hi) = rng.choice(PRODUCTS)
            people = rng.randint(2, 8)
            slots, price = people - 1, round(rng.randint(lo, hi), -2)
            image = rng.choice(images) if rng.random() < 0.3 else None
            kind = rng.random()
            if kind < 0.80:  # 모집 중
                filled = others(owner, rng.randint(0, slots - 1) if slots > 1 else 0)
                add(owner, title, category, "GROUP_BUY", slots, price, now + timedelta(hours=rng.randint(2, 240)), "OPEN", filled, lat, lng, image)
            elif kind < 0.90:  # 성사
                add(owner, title, category, "GROUP_BUY", slots, price, now + timedelta(hours=rng.randint(1, 72)), "CONFIRMED", others(owner, slots), lat, lng, image)
            elif kind < 0.96:  # 무산(마감이 지났고 몫이 안 참)
                add(owner, title, category, "GROUP_BUY", slots, price, now - timedelta(hours=rng.randint(1, 72)), "FAILED", others(owner, rng.randint(0, slots - 1) if slots > 1 else 0), lat, lng, image)
            else:  # 개설자가 취소
                add(owner, title, category, "GROUP_BUY", slots, price, now + timedelta(hours=rng.randint(1, 72)), "CANCELED", others(owner, rng.randint(0, slots - 1) if slots > 1 else 0), lat, lng, image)

        # ---- 시연 시나리오: 망원동의 데모 개설자 글 ----
        mw = home[owner_id]
        add(owner_id, "샤인머스켓 2kg 같이 사요", "FRUIT_VEG", "GROUP_BUY", 4, 25000, now + timedelta(days=2), "OPEN", others(owner_id, 3), mw[0], mw[1], images[0])  # 마지막 1몫: 동시 신청 시연용
        add(owner_id, "휴지 30롤 두 팩", "HOUSEHOLD", "GROUP_BUY", 2, 30000, now + timedelta(days=3), "OPEN", [], mw[0], mw[1], None)
        add(owner_id, "남은 두부 반 모, 내일까지", "ETC", "SHARE", 1, 0, datetime.combine(now.astimezone(KST).date() + timedelta(days=2), datetime.min.time(), KST), "OPEN", [], mw[0], mw[1], images[3])  # fmt: skip

        item_ids = [r[0] for r in conn.execute(insert(Item.__table__).returning(Item.id, sort_by_parameter_order=True), items)]
        reservations = [dict(item_id=i, user_id=u) for i, f in zip(item_ids, fills) for u in f]
        if reservations:
            conn.execute(insert(Reservation.__table__), reservations)

        n_share = sum(1 for i in items if i["type"] == "SHARE")
        print(f"사용자 {len(users)}명(시연 계정 2개 포함), 글 {len(items)}건(나눔 {n_share}), 신청 {len(reservations)}건")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--count", type=int, default=1000)
    ap.add_argument("--clean", action="store_true", help="시드·데모 데이터만 지운다")
    args = ap.parse_args()
    try:
        pid = assert_dev_database(engine)
    except UnsafeDatabase as e:
        sys.exit(f"거부: {e}")
    print(f"대상 DB 프로젝트: {pid}")
    started = time.time()
    if args.clean:
        with engine.begin() as conn:
            clean(conn)
        print("시드·데모 데이터를 지웠습니다.")
        return
    build(args.count, upload_images())
    print(f"시연 계정: demo-owner@example.com / demo-guest@example.com  비밀번호 {DEMO_PASSWORD}")
    print(f"걸린 시간 {time.time() - started:.1f}초")


if __name__ == "__main__":
    main()
