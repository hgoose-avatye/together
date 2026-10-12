"""부담금 규칙(기획서 5.3). 계산 함수만 검사하므로 DB가 필요 없다.

참여자 부담금 P = 10 × ⌊총액 ÷ (10 × n)⌋   (n = 나 포함 인원 = 몫 수 + 1)
개설자 부담금   = 총액 − 몫 수 × P
"""

import pytest

from app.pricing import split_price


@pytest.mark.parametrize(
    "total_price, total_slots, participant, owner",
    [
        (10_000, 2, 3_330, 3_340),  # 나 포함 3명 (기획서 예시)
        (25_000, 5, 4_160, 4_200),  # 나 포함 6명 (API 예시)
        (50_000, 5, 8_330, 8_350),
        (10_000, 20, 470, 600),  # 나 포함 21명: 개설자 추가 부담이 가장 큰 경우
        (10_000, 1, 5_000, 5_000),  # 나 포함 2명 (데모의 1몫 글)
        (9_999, 2, 3_330, 3_339),  # 10원 단위로 떨어지지 않는 총액
        (0, 3, 0, 0),
        (5, 1, 0, 5),  # 10원보다 작으면 참여자는 0원, 전부 개설자가 부담
    ],
)
def test_split_price_examples(total_price, total_slots, participant, owner):
    assert split_price(total_price, total_slots) == (participant, owner)


def test_total_always_matches_and_owner_extra_is_bounded():
    """모든 조합에서 합계가 총액과 정확히 같고, 개설자가 더 내는 금액은 인원 × 10원 미만이다."""
    for total_slots in range(1, 21):
        n = total_slots + 1
        for total_price in list(range(0, 2_000)) + [12_345, 99_999, 500_000, 1_000_000]:
            participant, owner = split_price(total_price, total_slots)
            assert participant * total_slots + owner == total_price
            assert participant % 10 == 0  # 10원 단위
            assert participant >= 0
            assert owner >= participant  # 개설자가 참여자보다 적게 내는 일은 없다
            assert owner - participant < 10 * n
