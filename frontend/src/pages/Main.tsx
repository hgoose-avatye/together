import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { NEIGHBORHOODS } from '../neighborhoods'
import { ApiError, token } from '../api'
import ReportDialog, { type ReportTarget } from '../components/ReportDialog'
import SafetyNotice from '../components/SafetyNotice'
import UserMenu from '../components/UserMenu'
import { getMe, joinItem, listItems } from '../endpoints'
import { remaining, untilDate, won } from '../format'
import type { Item } from '../types'

type Result = { key: string; items?: Item[]; error?: string }
type Sort = 'distance' | 'deadline'
type Tab = 'GROUP_BUY' | 'SHARE'
const RADII = [3, 5] as const
const GUEST_HOOD_KEY = 'gachi_guest_hood'

// 로그인 전에 고른 동네는 기억해 둔다. 저장소를 못 쓰는 브라우저면 기본 동네로 둘러본다.
function loadGuestHood(): string {
  try {
    const saved = localStorage.getItem(GUEST_HOOD_KEY)
    if (saved && NEIGHBORHOODS.some((n) => n.name === saved)) return saved
  } catch {
    /* 저장소를 못 쓰면 기본값 */
  }
  return NEIGHBORHOODS[0].name
}

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
  const [loggedIn, setLoggedIn] = useState(() => !!token.get())
  const [guestHood, setGuestHood] = useState(loadGuestHood)
  const [tab, setTab] = useState<Tab>('GROUP_BUY')
  const [sortChoice, setSortChoice] = useState<Sort | null>(null)
  // 정렬을 고르기 전에는 탭마다 기본값을 쓴다: 같이사기는 가까운 순, 나눔은 유통기한 임박 순(기획서 F-07)
  const sort: Sort = sortChoice ?? (tab === 'SHARE' ? 'deadline' : 'distance')
  const [radius, setRadius] = useState<(typeof RADII)[number]>(5)
  const [q, setQ] = useState('')
  const debouncedQ = useDebounced(q, 300)
  const [reload, setReload] = useState(0)
  const [result, setResult] = useState<Result | null>(null)
  const [now, setNow] = useState(Date.now)
  const [confirming, setConfirming] = useState<Item | null>(null)
  const [joining, setJoining] = useState<number | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [reporting, setReporting] = useState<ReportTarget | null>(null)
  // 지금의 인증 여부는 서버에 물어본다(다른 기기에서 인증했을 수 있다). 모르거나 실패하면 띠를 보이지 않는다.
  const [unverified, setUnverified] = useState(false)
  useEffect(() => {
    if (!loggedIn) return
    let stale = false
    getMe()
      .then((u) => !stale && setUnverified(!u.email_verified))
      .catch(() => {})
    return () => {
      stale = true
    }
  }, [loggedIn])

  // 로그인이 필요한 일은 로그인 화면으로 보낸다. 로그인하면 이 화면으로 돌아온다(기획서 11장).
  const toLogin = () => nav('/login?next=%2F')

  // 같은 key의 응답만 쓴다. 검색어를 빨리 바꿔도 늦게 온 옛 응답이 화면을 덮지 않는다.
  const key = `${loggedIn ? 'me' : guestHood}|${tab}|${sort}|${radius}|${debouncedQ}|${reload}`
  useEffect(() => {
    let stale = false
    // 로그인했으면 내 저장 위치가 기준이고, 아니면 고른 동네의 좌표를 보낸다
    const hood = NEIGHBORHOODS.find((n) => n.name === guestHood) ?? NEIGHBORHOODS[0]
    listItems({
      type: tab,
      sort,
      radius,
      q: debouncedQ,
      ...(!loggedIn && { lat: hood.lat, lng: hood.lng }),
    })
      .then((r) => !stale && setResult({ key, items: r.items }))
      .catch((e) => {
        if (stale) return
        if (e instanceof ApiError && e.field === 'lat' && loggedIn) {
          // 저장된 토큰이 더는 쓸 수 없는 경우(만료 등): 로그인 전 상태로 바꿔 다시 불러온다
          token.clear()
          setLoggedIn(false)
          return
        }
        setResult({ key, error: e instanceof ApiError ? e.message : '목록을 불러오지 못했어요' })
      })
    return () => {
      stale = true
    }
  }, [key, tab, sort, radius, debouncedQ, loggedIn, guestHood])

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
          <UserMenu
            loggedIn={loggedIn}
            unverified={unverified}
            onLogout={() => {
              token.clear()
              setLoggedIn(false)
              setUnverified(false)
            }}
          />
        </div>
        <input
          type="search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          maxLength={50}
          placeholder="품목을 검색해 보세요"
          className="mt-3 w-full rounded-lg bg-gray-100 px-3 py-2.5"
        />
        {!loggedIn && (
          <label className="mt-2 flex items-center gap-2 text-sm text-gray-600">
            내 동네
            <select
              value={guestHood}
              onChange={(e) => {
                setGuestHood(e.target.value)
                try {
                  localStorage.setItem(GUEST_HOOD_KEY, e.target.value)
                } catch {
                  /* 기억하지 못해도 이번 화면은 동작한다 */
                }
              }}
              className="rounded-lg bg-gray-100 px-2 py-1.5"
            >
              {NEIGHBORHOODS.map((n) => (
                <option key={n.name}>{n.name}</option>
              ))}
            </select>
          </label>
        )}
        <div className="mt-3 grid grid-cols-2 rounded-lg bg-gray-100 p-1 text-center text-sm">
          {(['GROUP_BUY', 'SHARE'] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`rounded-md py-1.5 font-medium ${tab === t ? 'bg-white shadow' : 'text-gray-500'}`}
            >
              {t === 'SHARE' ? '같이 마감하기' : '같이 사기'}
            </button>
          ))}
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
          {(['distance', 'deadline'] as const).map((s) => (
            <button
              key={s}
              onClick={() => setSortChoice(s)}
              className={`rounded-full px-3 py-1 ${sort === s ? 'bg-blue-600 text-white' : 'bg-gray-100'}`}
            >
              {s === 'distance'
                ? '가까운 순'
                : tab === 'SHARE'
                  ? '유통기한 임박 순'
                  : '마감 임박 순'}
            </button>
          ))}
          <span className="ml-auto flex gap-1" role="group" aria-label="반경">
            {RADII.map((r) => (
              <button
                key={r}
                onClick={() => setRadius(r)}
                aria-pressed={radius === r}
                className={`rounded-full px-3 py-1 ${radius === r ? 'bg-gray-800 text-white' : 'bg-gray-100'}`}
              >
                {r}km
              </button>
            ))}
          </span>
        </div>
      </header>

      {unverified && (
        <Link
          to="/check-email"
          className="mx-4 mt-3 block rounded-lg bg-amber-50 px-3 py-2.5 text-sm text-amber-900"
        >
          <b>이메일 인증이 필요해요.</b> 글을 올리고 신청하려면 인증을 마쳐 주세요 →
        </Link>
      )}

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
            onJoin={() => (loggedIn ? setConfirming(item) : toLogin())}
            loggedIn={loggedIn}
            onReport={() =>
              loggedIn
                ? setReporting({
                    itemId: item.id,
                    label: `${item.owner_nickname}님의 글 「${item.title}」`,
                  })
                : toLogin()
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
            to={tab === 'SHARE' ? '/new?type=SHARE' : '/new'}
            className="mt-4 inline-block rounded-lg bg-blue-600 px-4 py-2.5 font-semibold text-white"
          >
            글쓰기
          </Link>
        </div>
      )}

      <div className="pointer-events-none sticky bottom-6 mt-6 flex justify-end px-4">
        <Link
          to={tab === 'SHARE' ? '/new?type=SHARE' : '/new'}
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
              {confirming.type === 'SHARE'
                ? '무료로 받을까요?'
                : `몫당 ${won(confirming.price_per_slot)}으로 신청할까요?`}
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
  loggedIn,
}: {
  item: Item
  now: number
  busy: boolean
  onJoin: () => void
  onReport: () => void
  loggedIn: boolean
}) {
  const left = remaining(item.deadline, now)
  const share = item.type === 'SHARE'
  const pct = Math.round((item.filled_slots / item.total_slots) * 100)
  const disabled = busy || item.is_joined || left === null
  return (
    <li className="rounded-xl border border-gray-200 p-4">
      {item.image_url && (
        <img
          src={item.image_url}
          alt={item.title}
          loading="lazy"
          className={`mb-3 w-full rounded-lg object-cover ${share ? 'h-56' : 'h-32'}`}
        />
      )}
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
        {share ? (
          <span className="font-semibold">무료 나눔</span>
        ) : (
          <>
            <span className="font-semibold">{won(item.price_per_slot)}</span>
            <span className="text-sm text-gray-500"> · 총 {won(item.total_price)}</span>
          </>
        )}
      </p>
      <div className={`mt-2 items-center gap-2 text-sm ${share ? 'hidden' : 'flex'}`}>
        <div className="h-2 flex-1 overflow-hidden rounded-full bg-gray-100">
          <div className="h-full bg-blue-500" style={{ width: `${pct}%` }} />
        </div>
        <span>
          {item.filled_slots}/{item.total_slots}
        </span>
      </div>
      <div className="mt-3 flex items-center justify-between gap-2">
        <span className={`text-sm ${left ? 'text-gray-600' : 'text-red-600'}`}>
          {left === null ? '마감' : share ? untilDate(item.deadline) : left}
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
              {item.is_joined
                ? share
                  ? '받음'
                  : '신청함'
                : busy
                  ? '신청 중…'
                  : (loggedIn ? '' : '로그인하고 ') + (share ? '받기' : '신청')}
            </button>
          )}
        </div>
      </div>
    </li>
  )
}
