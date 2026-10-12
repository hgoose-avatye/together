"""부담금 규칙(기획서 5.3).

개설자도 인원 n(= 몫 수 + 1)에 포함된다. 참여자는 모두 같은 금액을 10원 단위로 내림해서 내고,
남는 금액은 개설자가 부담한다. 합계는 항상 총액과 정확히 같다.
"""


def split_price(total_price: int, total_slots: int) -> tuple[int, int]:
    """(참여자 부담금, 개설자 부담금)을 돌려준다. total_slots는 이웃에게 나눌 몫 수다."""
    n = total_slots + 1
    participant = 10 * (total_price // (10 * n))
    owner = total_price - total_slots * participant
    return participant, owner
