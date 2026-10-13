import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { ApiError, token } from '../api'
import ReportDialog, { type ReportTarget } from '../components/ReportDialog'
import SafetyNotice from '../components/SafetyNotice'
import { joinItem, listItems } from '../endpoints'
import { remaining, won } from '../format'
import type { Item } from '../types'

type Result = { key: string; items?: Item[]; error?: string }
type Sort = 'distance' | 'deadline'

function useDebounced<T>(value: T, ms: number) {
  const [v, setV] = useState(value)
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms)
    return () => clearTimeout(t)
  }, [value, ms])
  return v
}

export default function Main() {
  const nav = useNavigate()
  const [sort, setSort] = useState<Sort>('distance')
  const [q, setQ] = useState('')
  const debouncedQ = useDebounced(q, 300)
  const [reload, setReload] = useState(0)
  const [result, setResult] = useState<Result | null>(null)
  const [now, setNow] = useState(Date.now)
  const [confirming, setConfirming] = useState<Item | null>(null)
  const [joining, setJoining] = useState<number | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [reporting, setReporting] = useState<ReportTarget | null>(null)

  // 같은 key의 응답만 쓴다. 검색어를 빨리 바꿔도 늦게 온 옛 응답이 화면을 덮지 않는다.
  const key = `${sort}|${debouncedQ}|${reload}`
  useEffect(() => {
    let stale = false
    listItems({ type: 'GROUP_BUY', sort, q: debouncedQ })
      .then((r) => !stale && setResult({ key, items: r.items }))
      .catch(
        (e) =>
          !stale &&
          setResult({ key, error: e instanceof ApiError ? e.message : '목록을 불러오지 못했어요' }),
      )
    return () => {
      stale = true
    }
  }, [key, sort, debouncedQ])

  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 30_000)
    return () => clearInterval(t)
  }, [])

  useEffect(() => {
    if (!notice) return
    const t = setTimeout(() => setNotice(null), 4000)
    return () => clearTimeout(t)
  }, [notice])

  async function confirmJoin(item: Item) {
    setConfirming(null)
    setJoining(item.id) // 누르는 즉시 비활성화해 더블클릭을 막는다
    try {
      const r = await joinItem(item.id)
      setNotice(r.status === 'CONFIRMED' ? '마지막 몫을 가져갔어요. 성사됐어요!' : '신청했어요')
    } catch (e) {
      if (e instanceof ApiError && e.code === 'EMAIL_NOT_VERIFIED') {
        nav('/check-email') // 인증 안내 화면(기획서 11장)
        return
      }
      setNotice(e instanceof ApiError ? e.message : '서버에 연결하지 못했어요')
    } finally {
      setJoining(null)
      setReload((n) => n + 1) // 성공이든 실패든 목록을 새로고침한다
    }
  }

  const loading = result?.key !== key
  const items = result?.items ?? []

  return (
    <main className="pb-6">
      <header className="sticky top-0 z-10 bg-white px-4 pt-4 pb-3 shadow-sm">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-bold">같이</h1>
          <nav className="flex items-center gap-4 text-sm">
            <Link to="/me" className="font-medium text-blue-600">
              내 활동
            </Link>
            <button
              className="text-gray-500"
              onClick={() => {
                token.clear()
                nav('/login', { replace: true })
              }}
            >
              로그아웃
            </button>
          </nav>
        </div>
        <input
          type="search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          maxLength={50}
          placeholder="품목을 검색해 보세요"
          className="mt-3 w-full rounded-lg bg-gray-100 px-3 py-2.5"
        />
        <div className="mt-2 flex gap-2 text-sm">
          {(['distance', 'deadline'] as const).map((s) => (
            <button
              key={s}
              onClick={() => setSort(s)}
              className={`rounded-full px-3 py-1 ${sort === s ? 'bg-blue-600 text-white' : 'bg-gray-100'}`}
            >
              {s === 'distance' ? '가까운 순' : '마감 임박 순'}
            </button>
          ))}
        </div>
      </header>

      {notice && (
        <p
          role="status"
          className="mx-4 mt-3 rounded-lg bg-gray-900 px-3 py-2.5 text-sm text-white"
        >
          {notice}
        </p>
      )}

      <ul className="mt-3 space-y-3 px-4">
        {items.map((item) => (
          <ItemCard
            key={item.id}
            item={item}
            now={now}
            busy={joining === item.id}
            onJoin={() => setConfirming(item)}
            onReport={() =>
              setReporting({
                itemId: item.id,
                label: `${item.owner_nickname}님의 글 「${item.title}」`,
              })
            }
          />
        ))}
      </ul>

      {!loading && result?.error && (
        <p className="px-4 py-10 text-center text-red-600">{result.error}</p>
      )}
      {loading && items.length === 0 && (
        <p className="px-4 py-10 text-center text-gray-500">불러오는 중…</p>
      )}
      {!loading && !result?.error && items.length === 0 && (
        <div className="px-4 py-16 text-center">
          <p className="text-gray-600">
            {debouncedQ ? '검색 결과가 없어요' : '근처에 글이 없어요'}
          </p>
          <Link
            to="/new"
            className="mt-4 inline-block rounded-lg bg-blue-600 px-4 py-2.5 font-semibold text-white"
          >
            글쓰기
          </Link>
        </div>
      )}

      <div className="pointer-events-none sticky bottom-6 mt-6 flex justify-end px-4">
        <Link
          to="/new"
          aria-label="글쓰기"
          className="pointer-events-auto flex h-14 w-14 items-center justify-center rounded-full bg-blue-600 text-3xl text-white shadow-lg"
        >
          +
        </Link>
      </div>

      {confirming && (
        <div
          className="fixed inset-0 z-20 flex items-end justify-center bg-black/40"
          onClick={() => setConfirming(null)}
        >
          <div
            className="w-full max-w-[430px] rounded-t-2xl bg-white p-5"
            onClick={(e) => e.stopPropagation()}
          >
            <p className="text-lg font-semibold">{confirming.title}</p>
            <p className="mt-2 text-gray-700">
              몫당 {won(confirming.price_per_slot)}으로 신청할까요?
            </p>
            <p className="mt-1 text-sm text-red-600">신청 후에는 취소할 수 없어요.</p>
            <SafetyNotice className="mt-3" />
            <div className="mt-5 grid grid-cols-2 gap-2">
              <button className="rounded-lg bg-gray-100 py-3" onClick={() => setConfirming(null)}>
                취소
              </button>
              <button
                className="rounded-lg bg-blue-600 py-3 font-semibold text-white"
                onClick={() => confirmJoin(confirming)}
              >
                신청하기
              </button>
            </div>
          </div>
        </div>
      )}
      {reporting && (
        <ReportDialog
          target={reporting}
          onClose={() => setReporting(null)}
          onDone={(m) => {
            setReporting(null)
            setNotice(m)
          }}
        />
      )}
    </main>
  )
}

function ItemCard({
  item,
  now,
  busy,
  onJoin,
  onReport,
}: {
  item: Item
  now: number
  busy: boolean
  onJoin: () => void
  onReport: () => void
}) {
  const left = remaining(item.deadline, now)
  const pct = Math.round((item.filled_slots / item.total_slots) * 100)
  const disabled = busy || item.is_joined || left === null
  return (
    <li className="rounded-xl border border-gray-200 p-4">
      <div className="flex items-start justify-between gap-2">
        <h2 className="font-semibold">{item.title}</h2>
        <span className="shrink-0 text-xs text-gray-500">{item.distance_km}km</span>
      </div>
      <p className="mt-0.5 flex items-center gap-2 text-sm text-gray-500">
        {item.owner_nickname}
        {!item.is_mine && (
          <button className="text-xs text-gray-400 underline" onClick={onReport}>
            신고
          </button>
        )}
      </p>
      <p className="mt-2">
        <span className="font-semibold">{won(item.price_per_slot)}</span>
        <span className="text-sm text-gray-500"> · 총 {won(item.total_price)}</span>
      </p>
      <div className="mt-2 flex items-center gap-2 text-sm">
        <div className="h-2 flex-1 overflow-hidden rounded-full bg-gray-100">
          <div className="h-full bg-blue-500" style={{ width: `${pct}%` }} />
        </div>
        <span>
          {item.filled_slots}/{item.total_slots}
        </span>
      </div>
      <div className="mt-3 flex items-center justify-between gap-2">
        <span className={`text-sm ${left ? 'text-gray-600' : 'text-red-600'}`}>
          {left ?? '마감'}
        </span>
        <div className="flex items-center gap-2">
          {item.product_url && (
            <a
              href={item.product_url}
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-lg bg-gray-100 px-3 py-2 text-sm"
            >
              상품 보기
            </a>
          )}
          {!item.is_mine && (
            <button
              disabled={disabled}
              onClick={onJoin}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white disabled:bg-gray-300"
            >
              {item.is_joined ? '신청함' : busy ? '신청 중…' : '신청'}
            </button>
          )}
        </div>
      </div>
    </li>
  )
}
