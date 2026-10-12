import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router'
import { ApiError } from '../api'
import { createItem } from '../endpoints'
import { splitPrice, won } from '../format'

const pad = (n: number) => String(n).padStart(2, '0')
/** <input type="datetime-local">이 쓰는 'YYYY-MM-DDTHH:mm' (브라우저 시간대) */
const toLocalInput = (d: Date) =>
  `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`

export default function NewItem() {
  const nav = useNavigate()
  const [title, setTitle] = useState('')
  const [price, setPrice] = useState('')
  const [people, setPeople] = useState('3') // 나 포함 인원
  const [deadline, setDeadline] = useState(() =>
    toLocalInput(new Date(Date.now() + 24 * 3600 * 1000)),
  )
  // 마감 입력의 선택 범위(지금 ~ 30일 뒤). 렌더링마다 바뀌지 않게 한 번만 계산한다
  const [bounds] = useState(() => ({
    min: toLocalInput(new Date()),
    max: toLocalInput(new Date(Date.now() + 30 * 24 * 3600 * 1000)),
  }))
  const [note, setNote] = useState('')
  const [url, setUrl] = useState('')
  const [problem, setProblem] = useState<{ message: string; field?: string } | null>(null)
  const [busy, setBusy] = useState(false)

  const total = Number(price)
  const n = Number(people)
  const valid =
    price !== '' &&
    Number.isInteger(total) &&
    total >= 0 &&
    Number.isInteger(n) &&
    n >= 2 &&
    n <= 21
  const split = valid ? splitPrice(total, n) : null // 미리보기일 뿐이고 실제 금액은 서버가 정한다

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (busy) return
    setProblem(null)
    setBusy(true)
    try {
      await createItem({
        type: 'GROUP_BUY',
        title,
        total_slots: n - 1, // 서버는 '이웃에게 나눌 몫' = 나 포함 인원 - 1을 받는다
        total_price: total,
        deadline: new Date(deadline).toISOString(),
        pickup_note: note,
        ...(url.trim() && { product_url: url.trim() }),
      })
      nav('/', { replace: true })
    } catch (err) {
      setProblem(
        err instanceof ApiError
          ? { message: err.message, field: err.field }
          : { message: '서버에 연결하지 못했어요. 잠시 뒤 다시 시도해 주세요' },
      )
    } finally {
      setBusy(false)
    }
  }

  // 서버 필드 이름(total_slots)과 화면의 입력 이름(people)이 달라서 짝을 지어 준다
  const err = (field: string) =>
    problem?.field === field ? <p className="mt-1 text-sm text-red-600">{problem.message}</p> : null
  const box = 'mt-1 w-full rounded-lg border border-gray-300 px-3 py-2.5 text-base'

  return (
    <main className="px-4 py-6">
      <Link to="/" className="text-sm text-gray-500">
        ← 목록으로
      </Link>
      <h1 className="mt-2 text-xl font-bold">같이 살 사람 모으기</h1>

      <form onSubmit={submit} className="mt-5 space-y-4">
        <label className="block">
          무엇을 살까요?
          <input
            className={box}
            required
            maxLength={50}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="샤인머스켓 2kg 나눠요"
          />
          {err('title')}
        </label>

        <label className="block">
          총 가격 (원)
          <input
            className={box}
            type="number"
            inputMode="numeric"
            required
            min={0}
            max={1000000}
            step={1}
            value={price}
            onChange={(e) => setPrice(e.target.value)}
          />
          {err('total_price')}
        </label>

        <label className="block">
          나 포함 몇 명이서 나눌까요?
          <input
            className={box}
            type="number"
            inputMode="numeric"
            required
            min={2}
            max={21}
            value={people}
            onChange={(e) => setPeople(e.target.value)}
          />
          <span className="mt-1 block text-xs text-gray-500">나도 한 몫을 가져가요. 2~21명</span>
          {err('total_slots')}
        </label>

        <p className="rounded-lg bg-blue-50 px-3 py-3 text-sm" aria-live="polite">
          {split && n >= 2 ? (
            <>
              참여자 {n - 1}명 × <b>{won(split.participant)}</b> · 내 몫 <b>{won(split.owner)}</b> ·
              총 {won(total)}
              <span className="mt-1 block text-xs text-gray-500">
                10원 단위 아래로 남는 금액은 글을 올린 사람이 내요.
              </span>
            </>
          ) : (
            '가격과 인원을 입력하면 각자 낼 금액이 보여요'
          )}
        </p>

        <label className="block">
          모집 마감
          <input
            className={box}
            type="datetime-local"
            required
            min={bounds.min}
            max={bounds.max}
            value={deadline}
            onChange={(e) => setDeadline(e.target.value)}
          />
          {err('deadline')}
        </label>

        <label className="block">
          만남 장소 메모
          <textarea
            className={box}
            required
            maxLength={200}
            rows={3}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="○○아파트 정문, 토 오후 3시, 오픈채팅 링크"
          />
          <span className="mt-1 block text-xs text-gray-500">
            장소·시간·연락 방법을 함께 적어 주세요. 몫이 모두 차서 성사된 뒤에만 참여자에게 보여요.
          </span>
          {err('pickup_note')}
        </label>

        <label className="block">
          상품 링크 (선택)
          <input
            className={box}
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://"
          />
          {err('product_url')}
        </label>

        <p className="text-xs text-gray-500">
          정산은 참여하는 분들끼리 직접 해요. 같이는 금액을 받거나 관여하지 않아요.
        </p>

        {problem && !problem.field && (
          <p role="alert" className="text-sm text-red-600">
            {problem.message}
          </p>
        )}

        <button
          disabled={busy}
          className="w-full rounded-lg bg-blue-600 py-3 font-semibold text-white disabled:opacity-50"
        >
          {busy ? '올리는 중…' : '올리기'}
        </button>
      </form>
    </main>
  )
}
