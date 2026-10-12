"""A-03 목록 조회. 개발용 Supabase DB에 실제로 쓴다.

테스트마다 서로 멀리 떨어진 위치(unique_location)를 써서 다른 테스트의 글이 섞이지 않게 한다.
"""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from .conftest import make_user
from .helpers import insert_item, insert_reservation, offset, unique_location

NOW = lambda: datetime.now(timezone.utc)  # noqa: E731


def titles(res) -> list[str]:
    assert res.status_code == 200, res.text
    return [i["title"] for i in res.json()["items"]]


def list_items(client: TestClient, user, **params):
    params.setdefault("type", "GROUP_BUY")
    return client.get("/items", params=params, headers=user.headers)


# ---------- 기본 동작과 응답 형식 ----------


def test_list_shows_created_item_with_expected_fields(client: TestClient):
    loc = unique_location()
    owner = make_user(client, nickname="개설자", lat=loc[0], lng=loc[1])
    viewer = make_user(client, nickname="구경꾼", lat=loc[0], lng=loc[1])
    created = client.post(
        "/items",
        json={
            "type": "GROUP_BUY",
            "title": "샤인머스켓 2kg 나눠요",
            "total_slots": 5,
            "total_price": 25_000,
            "deadline": (
                datetime.now(timezone(timedelta(hours=9))) + timedelta(days=1)
            ).isoformat(),
            "pickup_note": "비밀 만남 장소 메모",
            "product_url": "https://example.com/p/1",
        },
        headers=owner.headers,
    ).json()

    res = list_items(client, viewer)
    [item] = res.json()["items"]
    assert item["id"] == created["id"]
    assert item["owner_nickname"] == "개설자"
    assert (item["total_slots"], item["filled_slots"], item["remaining_slots"]) == (
        5,
        0,
        5,
    )
    assert (item["total_price"], item["price_per_slot"]) == (25_000, 4_160)
    assert item["status"] == "OPEN"
    assert item["distance_km"] == 0.0
    assert item["is_mine"] is False and item["is_joined"] is False
    assert item["product_url"] == "https://example.com/p/1"
    assert item["deadline"].endswith("+09:00")
    # 만남 장소 메모와 개설자 부담금은 목록에 절대 나가지 않는다.
    assert "pickup_note" not in item and "owner_share" not in item
    assert "비밀 만남 장소 메모" not in res.text

    assert list_items(client, owner).json()["items"][0]["is_mine"] is True


def test_empty_list_when_nothing_nearby(client: TestClient):
    loc = unique_location()
    me = make_user(client, lat=loc[0], lng=loc[1])
    res = list_items(client, me)
    assert res.status_code == 200
    assert res.json() == {"items": []}


# ---------- 어떤 글이 보이는가 ----------


def test_only_open_items_before_deadline_are_listed(client: TestClient):
    loc = unique_location()
    me = make_user(client, lat=loc[0], lng=loc[1])
    insert_item(me.id, loc, title="보이는 글")
    insert_item(
        me.id, loc, title="마감 지남", deadline=NOW() - timedelta(minutes=1)
    )  # 저장값은 OPEN
    insert_item(me.id, loc, title="성사", status="CONFIRMED", filled_slots=3)
    insert_item(me.id, loc, title="무산", status="FAILED")
    insert_item(me.id, loc, title="취소", status="CANCELED")
    assert titles(list_items(client, me)) == ["보이는 글"]


def test_type_tab_separates_group_buy_and_share(client: TestClient):
    loc = unique_location()
    me = make_user(client, lat=loc[0], lng=loc[1])
    insert_item(me.id, loc, title="공구")
    insert_item(me.id, loc, title="나눔", type="SHARE")
    assert titles(list_items(client, me, type="GROUP_BUY")) == ["공구"]
    assert titles(list_items(client, me, type="SHARE")) == ["나눔"]


def test_is_joined_is_per_viewer(client: TestClient):
    loc = unique_location()
    owner = make_user(client, lat=loc[0], lng=loc[1])
    joiner = make_user(client, lat=loc[0], lng=loc[1])
    other = make_user(client, lat=loc[0], lng=loc[1])
    item_id = insert_item(owner.id, loc, filled_slots=1)
    insert_reservation(item_id, joiner.id)

    assert list_items(client, joiner).json()["items"][0]["is_joined"] is True
    assert list_items(client, other).json()["items"][0]["is_joined"] is False
    assert list_items(client, owner).json()["items"][0]["is_joined"] is False


# ---------- 위치와 반경 ----------


def test_radius_filters_by_real_distance(client: TestClient):
    loc = unique_location()
    me = make_user(client, lat=loc[0], lng=loc[1])
    insert_item(me.id, offset(loc, dlat=0.02), title="약 2.2km")
    insert_item(me.id, offset(loc, dlat=0.04), title="약 4.4km")
    insert_item(me.id, offset(loc, dlat=0.06), title="약 6.7km")

    assert titles(list_items(client, me, radius=3)) == ["약 2.2km"]
    assert titles(list_items(client, me, radius=5)) == ["약 2.2km", "약 4.4km"]
    assert titles(list_items(client, me)) == ["약 2.2km", "약 4.4km"]  # 기본 반경은 5km


def test_radius_uses_distance_not_just_the_bounding_box(client: TestClient):
    """사각형 범위의 모서리(대각선)는 반경 밖이므로 걸러져야 한다."""
    loc = unique_location()
    me = make_user(client, lat=loc[0], lng=loc[1])
    # 위도 0.04(약 4.4km) + 경도 0.04(약 3.6km) = 대각선 약 5.7km
    insert_item(me.id, offset(loc, dlat=0.04, dlng=0.04), title="모서리")
    assert titles(list_items(client, me, radius=5)) == []


def test_custom_center_and_distance_from_it(client: TestClient):
    home = unique_location()
    elsewhere = unique_location()
    me = make_user(client, lat=home[0], lng=home[1])
    insert_item(me.id, home, title="우리 동네")
    insert_item(me.id, offset(elsewhere, dlat=0.02), title="다른 동네")

    assert titles(list_items(client, me)) == ["우리 동네"]
    res = list_items(client, me, lat=elsewhere[0], lng=elsewhere[1])
    assert titles(res) == ["다른 동네"]
    assert res.json()["items"][0]["distance_km"] == 2.2  # 기준점은 보낸 좌표다


def test_custom_center_is_rounded_to_two_decimals(client: TestClient):
    loc = unique_location()
    me = make_user(client, lat=loc[0] + 10, lng=loc[1])  # 내 위치는 멀리
    insert_item(me.id, loc, title="여기")
    res = list_items(client, me, lat=loc[0] + 0.0004, lng=loc[1] - 0.0004)  # 정밀 좌표
    assert titles(res) == ["여기"]
    assert res.json()["items"][0]["distance_km"] == 0.0


# ---------- 정렬 ----------


def test_sort_by_distance_then_deadline(client: TestClient):
    loc = unique_location()
    me = make_user(client, lat=loc[0], lng=loc[1])
    soon, later = NOW() + timedelta(hours=2), NOW() + timedelta(hours=20)
    insert_item(me.id, offset(loc, dlat=0.04), title="멀고 급함", deadline=soon)
    insert_item(me.id, offset(loc, dlat=0.02), title="가깝고 느긋", deadline=later)
    insert_item(
        me.id, offset(loc, dlat=0.02), title="가깝고 급함", deadline=soon
    )  # 같은 거리

    assert titles(list_items(client, me, sort="distance")) == [
        "가깝고 급함",
        "가깝고 느긋",
        "멀고 급함",
    ]


def test_sort_by_deadline(client: TestClient):
    loc = unique_location()
    me = make_user(client, lat=loc[0], lng=loc[1])
    insert_item(
        me.id, offset(loc, dlat=0.02), title="C", deadline=NOW() + timedelta(hours=30)
    )
    insert_item(
        me.id, offset(loc, dlat=0.04), title="A", deadline=NOW() + timedelta(hours=2)
    )
    insert_item(me.id, loc, title="B", deadline=NOW() + timedelta(hours=10))
    assert titles(list_items(client, me, sort="deadline")) == ["A", "B", "C"]


# ---------- 검색 ----------


def test_search_matches_title_partially_and_ignores_case(client: TestClient):
    loc = unique_location()
    me = make_user(client, lat=loc[0], lng=loc[1])
    for t in ("샤인머스켓 2kg", "계란 30구", "Large EGGS", "휴지 24롤"):
        insert_item(me.id, loc, title=t)

    assert titles(list_items(client, me, q="샤인")) == ["샤인머스켓 2kg"]
    assert titles(list_items(client, me, q="머스켓")) == ["샤인머스켓 2kg"]  # 부분 일치
    assert titles(list_items(client, me, q="eggs")) == ["Large EGGS"]  # 대소문자 무시
    assert sorted(titles(list_items(client, me, q=""))) == sorted(
        ["샤인머스켓 2kg", "계란 30구", "Large EGGS", "휴지 24롤"]
    )  # 빈 검색어는 전체
    assert titles(list_items(client, me, q="없는품목")) == []


def test_search_does_not_treat_wildcards_as_patterns(client: TestClient):
    loc = unique_location()
    me = make_user(client, lat=loc[0], lng=loc[1])
    for t in ("100% 오렌지", "사과 박스", "a_b 세트", "axb 세트", "역슬래시\\포함"):
        insert_item(me.id, loc, title=t)

    assert titles(list_items(client, me, q="%")) == [
        "100% 오렌지"
    ]  # 전부 매칭되면 안 된다
    assert titles(list_items(client, me, q="a_b")) == [
        "a_b 세트"
    ]  # _가 한 글자 와일드카드면 axb도 걸린다
    assert titles(list_items(client, me, q="\\")) == ["역슬래시\\포함"]


def test_search_is_limited_to_current_tab(client: TestClient):
    loc = unique_location()
    me = make_user(client, lat=loc[0], lng=loc[1])
    insert_item(me.id, loc, title="두부 공구", type="GROUP_BUY")
    insert_item(me.id, loc, title="두부 나눔", type="SHARE")
    assert titles(list_items(client, me, type="GROUP_BUY", q="두부")) == ["두부 공구"]
    assert titles(list_items(client, me, type="SHARE", q="두부")) == ["두부 나눔"]


# ---------- 입력 오류와 인증 ----------


@pytest.mark.parametrize(
    "params, field",
    [
        ({}, "type"),  # 필수
        ({"type": "X"}, "type"),
        ({"type": "GROUP_BUY", "sort": "price"}, "sort"),
        ({"type": "GROUP_BUY", "radius": 4}, "radius"),
        (
            {"type": "GROUP_BUY", "radius": 1},
            "radius",
        ),  # 위치를 흐려 저장하므로 1km는 제외
        ({"type": "GROUP_BUY", "radius": "abc"}, "radius"),
        ({"type": "GROUP_BUY", "q": "가" * 51}, "q"),
        ({"type": "GROUP_BUY", "lat": 37.5}, "lng"),  # 위도만
        ({"type": "GROUP_BUY", "lng": 127.0}, "lat"),  # 경도만
        ({"type": "GROUP_BUY", "lat": 91, "lng": 127}, "lat"),
        ({"type": "GROUP_BUY", "lat": "abc", "lng": 127}, "lat"),
    ],
)
def test_invalid_query_is_400_with_field(
    client: TestClient, shared_user, params, field
):
    res = client.get("/items", params=params, headers=shared_user.headers)
    assert res.status_code == 400, res.text
    body = res.json()
    assert (
        body["code"] == "INVALID_INPUT" and body["field"] == field and body["message"]
    )


@pytest.fixture(scope="module")
def shared_user(client: TestClient):
    return make_user(client)


def test_list_requires_login(client: TestClient):
    res = client.get("/items", params={"type": "GROUP_BUY"})
    assert res.status_code == 401
    assert res.json()["code"] == "UNAUTHORIZED"
