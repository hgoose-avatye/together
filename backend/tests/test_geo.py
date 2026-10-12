from app.geo import haversine_km


def test_same_point_is_zero():
    assert haversine_km(37.56, 126.90, 37.56, 126.90) == 0


def test_one_degree_of_latitude():
    # 지구 반지름 6371km 기준으로 위도 1도 = 약 111.19km
    assert abs(haversine_km(0, 0, 1, 0) - 111.19) < 0.01


def test_is_symmetric():
    a = haversine_km(37.5663, 126.9779, 37.4979, 127.0276)
    b = haversine_km(37.4979, 127.0276, 37.5663, 126.9779)
    assert a == b
    assert 8 < a < 10  # 서울시청 ~ 강남역은 약 9km
