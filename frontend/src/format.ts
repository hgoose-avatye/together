// 서버는 오프셋이 붙은 ISO 시각을 주고, 화면은 항상 한국 시간으로 보여 준다(기획서 5.3).
const KST = { timeZone: 'Asia/Seoul' } as const

export const won = (n: number) => `${n.toLocaleString('ko-KR')}원`

export const formatDateTime = (iso: string) =>
  new Intl.DateTimeFormat('ko-KR', {
    ...KST,
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(iso))

/** 마감까지 남은 시간. 0 이하이면 null(마감). */
export function remaining(iso: string, now = Date.now()): string | null {
  const ms = new Date(iso).getTime() - now
  if (ms <= 0) return null
  const min = Math.floor(ms / 60000)
  if (min < 60) return `${Math.max(min, 1)}분 남음`
  const hour = Math.floor(min / 60)
  return hour < 24
    ? `${hour}시간 ${min % 60}분 남음`
    : `${Math.floor(hour / 24)}일 ${hour % 24}시간 남음`
}

/** 나 포함 인원 n명으로 나눌 때의 부담금(기획서 5.3). 서버의 pricing.py와 같은 식이다. */
export function splitPrice(totalPrice: number, people: number) {
  const participant = 10 * Math.floor(totalPrice / (10 * people))
  return { participant, owner: totalPrice - (people - 1) * participant }
}
