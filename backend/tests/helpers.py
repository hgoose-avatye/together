"""API로는 만들 수 없는 상태(마감 지난 글, 성사된 글 등)를 DB에 직접 넣는 테스트 도구.

여기서 만든 글과 신청은 소유자가 pytest- 계정이라 conftest의 정리 단계에서 함께 지워진다.
"""

import itertools
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from app.db import engine
from app.pricing import split_price
from app.security import create_access_token

from .conftest import TestUser, new_email

_counter = itertools.count()


def unique_location() -> tuple[float, float]:
    """테스트마다 서로 멀리 떨어진(최소 약 22km) 위치를 돌려준다.

    목록 조회는 위치로 걸러지므로, 위치를 나눠 쓰면 다른 테스트의 글이 섞이지 않는다.
    """
    k = next(_counter)
    return round(33.0 + 0.2 * (k % 50), 2), round(124.0 + 0.2 * (k // 50), 2)


def offset(
    location: tuple[float, float], dlat: float = 0.0, dlng: float = 0.0
) -> tuple[float, float]:
    return round(location[0] + dlat, 2), round(location[1] + dlng, 2)


def insert_item(
    owner_id: int,
    location: tuple[float, float],
    *,
    title: str = "테스트 글",
    type: str = "GROUP_BUY",
    status: str = "OPEN",
    deadline: datetime | None = None,
    total_slots: int = 3,
    total_price: int = 10_000,
    filled_slots: int = 0,
    image_url: str | None = None,
) -> int:
    if type == "SHARE":  # 나눔은 1몫, 0원, 사진 필수(DB CHECK)
        total_slots, total_price = 1, 0
        image_url = image_url or "https://example.com/share.webp"
    price_per_slot, _ = split_price(total_price, total_slots)
    deadline = deadline or datetime.now(timezone.utc) + timedelta(days=1)
    with engine.begin() as conn:
        return conn.execute(
            text(
                """
                INSERT INTO items (owner_id, type, title, total_slots, total_price, price_per_slot,
                                   filled_slots, deadline, lat, lng, pickup_note, image_url, status)
                VALUES (:owner_id, :type, :title, :total_slots, :total_price, :price_per_slot,
                        :filled_slots, :deadline, :lat, :lng, '메모', :image_url, :status)
                RETURNING id
                """
            ),
            {
                "owner_id": owner_id,
                "type": type,
                "title": title,
                "total_slots": total_slots,
                "total_price": total_price,
                "price_per_slot": price_per_slot,
                "filled_slots": filled_slots,
                "deadline": deadline,
                "lat": location[0],
                "lng": location[1],
                "image_url": image_url,
                "status": status,
            },
        ).scalar_one()


def insert_reservation(item_id: int, user_id: int) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO reservations (item_id, user_id) VALUES (:i, :u)"),
            {"i": item_id, "u": user_id},
        )


def insert_user(location: tuple[float, float], nickname: str = "테스트유저") -> TestUser:
    """가입·로그인을 거치지 않고 사용자를 DB에 넣고 토큰을 바로 발급한다(bcrypt를 피해 빠르다).

    로그인 자체를 검사하는 테스트에는 쓰지 말 것: 비밀번호 해시가 가짜다.
    """
    email = new_email()
    with engine.begin() as conn:
        user_id = conn.execute(
            text(
                "INSERT INTO users (email, password_hash, nickname, lat, lng) "
                "VALUES (:email, 'not-a-real-hash', :nickname, :lat, :lng) RETURNING id"
            ),
            {"email": email, "nickname": nickname, "lat": location[0], "lng": location[1]},
        ).scalar_one()
    return TestUser(user_id, email, nickname, {"Authorization": f"Bearer {create_access_token(user_id)}"})


def item_row(item_id: int):
    with engine.connect() as conn:
        return conn.execute(text("SELECT * FROM items WHERE id = :id"), {"id": item_id}).one()


def reservation_count(item_id: int) -> int:
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT count(*) FROM reservations WHERE item_id = :id"), {"id": item_id}
        ).scalar_one()
