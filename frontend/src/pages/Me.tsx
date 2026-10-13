import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { ApiError } from '../api'
import ReportDialog, { type ReportTarget } from '../components/ReportDialog'
import SafetyNotice from '../components/SafetyNotice'
import { cancelItem, myItems, myReservations } from '../endpoints'
import { formatDateTime, untilDate, won } from '../format'
import type { ItemStatus, MyItem, Reservation } from '../types'

type Tab = 'reservations' | 'items'
type Data = { key: string; reservations?: Reservation[]; items?: MyItem[]; error?: string }

const STATUS: Record<ItemStatus, { label: string; color: string }> = {
  OPEN: { label: '모집 중', color: 'bg-blue-50 text-blue-700' },
  CONFIRMED: { label: '성사', color: 'bg-green-50 text-green-700' },
  FAILED: { label: '무산', color: 'bg-gray-100 text-gray-600' },
  CANCELED: { label: '취소', color: 'bg-gray-100 text-gray-600' },
}

const SUSPENDED_TEXT = '계정 이용이 제한됐어요. 만남 전에 직접 확인해 주세요.'

const SuspendedNote = ({ inline = false }: { inline?: boolean }) =>
  inline ? (
    <span className="text-xs text-red-600">{SUSPENDED_TEXT}</span>
  ) : (
    <p role="status" className="mt-3 rounded-lg bg-red-50 p-3 text-sm text-red-700">
      {SUSPENDED_TEXT}
    </p>
  )

// 나눔 글의 무산(FAILED)은 "무산" 대신 "마감"으로 보여 준다(기획서 5.4).
const Badge = ({ status, type }: { status: ItemStatus; type: string }) => (
  <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${STATUS[status].color}`}>
    {status === 'FAILED' && type === 'SHARE' ? '마감' : STATUS[status].label}
  </span>
)

export default function Me() {
  const [tab, setTab] = useState<Tab>('reservations')
  const [reload, setReload] = useState(0)
  const [data, setData] = useState<Data | null>(null)
  const [canceling, setCanceling] = useState<MyItem | null>(null)
  const [busyId, setBusyId] = useState<number | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [reporting, setReporting] = useState<ReportTarget | null>(null)

  // 같은 key의 응답만 쓴다. 탭을 빨리 바꿔도 늦게 온 옛 응답이 화면을 덮지 않는다.
  const key = `${tab}|${reload}`
  useEffect(() => {
    let stale = false
    const load =
      tab === 'reservations'
        ? myReservations().then((r) => ({ reservations: r.reservations }))
        : myItems().then((r) => ({ items: r.items }))
    load
      .then((d) => !stale && setData({ key, ...d }))
      .catch(
        (e) =>
          !stale &&
          setData({ key, error: e instanceof ApiError ? e.message : '불러오지 못했어요' }),
      )
    return () => {
      stale = true
    }
  }, [key, tab])

  useEffect(() => {
    if (!notice) return
    const t = setTimeout(() => setNotice(null), 4000)
    return () => clearTimeout(t)
  }, [notice])

  async function confirmCancel(item: MyItem) {
    setCanceling(null)
    setBusyId(item.id) // 누르는 즉시 비활성화해 중복 요청을 막는다
    try {
      await cancelItem(item.id)
      setNotice('모집을 취소했어요')
    } catch (e) {
      setNotice(e instanceof ApiError ? e.message : '서버에 연결하지 못했어요')
    } finally {
      setBusyId(null)
      setReload((n) => n + 1) // 성공이든 실패든 목록을 새로고침한다
    }
  }

  const loading = data?.key !== key
  const reservations = data?.reservations ?? []
  const items = data?.items ?? []
  const empty =
    !loading && !data?.error && (tab === 'reservations' ? reservations : items).length === 0

  return (
    <main className="pb-10">
      <header className="sticky top-0 z-10 bg-white px-4 pt-4 pb-3 shadow-sm">
        <Link to="/" className="text-sm text-gray-500">
          ← 목록으로
        </Link>
        <h1 className="mt-1 text-xl font-bold">내 활동</h1>
        <div className="mt-3 grid grid-cols-2 rounded-lg bg-gray-100 p-1 text-center">
          {(['reservations', 'items'] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`rounded-md py-2 font-medium ${tab === t ? 'bg-white shadow' : 'text-gray-500'}`}
            >
              {t === 'reservations' ? '내 참여' : '내 글'}
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
      {loading && <p className="px-4 py-10 text-center text-gray-500">불러오는 중…</p>}
      {!loading && data?.error && (
        <p className="px-4 py-10 text-center text-red-600">{data.error}</p>
      )}
      {empty && (
        <p className="px-4 py-16 text-center text-gray-500">
          {tab === 'reservations' ? '아직 신청한 글이 없어요' : '아직 올린 글이 없어요'}
        </p>
      )}

      {!loading && (
        <ul className="mt-3 space-y-3 px-4">
          {reservations.map((r) => (
            <li key={r.reservation_id} className="rounded-xl border border-gray-200 p-4">
              <div className="flex items-start justify-between gap-2">
                <h2 className="font-semibold">{r.item.title}</h2>
                <Badge status={r.item.status} type={r.item.type} />
              </div>
              <p className="mt-0.5 flex items-center gap-2 text-sm text-gray-500">
                {r.item.owner_nickname}
                <button
                  className="text-xs text-gray-400 underline"
                  onClick={() =>
                    setReporting({
                      itemId: r.item.id,
                      label: `${r.item.owner_nickname}님의 글 「${r.item.title}」`,
                    })
                  }
                >
                  신고
                </button>
              </p>
              <p className="mt-2">
                {r.item.type === 'SHARE' ? (
                  <b>무료 나눔</b>
                ) : (
                  <>
                    내 부담금 <b>{won(r.item.price_per_slot)}</b>
                  </>
                )}
              </p>
              <p className="mt-1 text-sm text-gray-500">
                {r.item.type === 'SHARE'
                  ? untilDate(r.item.deadline)
                  : `마감 ${formatDateTime(r.item.deadline)}`}{' '}
                · 신청 {formatDateTime(r.joined_at)}
              </p>
              {r.item.pickup_note ? (
                <p className="mt-3 rounded-lg bg-green-50 p-3 text-sm">
                  <b className="block text-green-800">만남 정보</b>
                  <span className="whitespace-pre-wrap">{r.item.pickup_note}</span>
                </p>
              ) : r.item.status === 'OPEN' ? (
                <p className="mt-3 text-sm text-gray-500">몫이 모두 차면 만남 장소가 열려요.</p>
              ) : null}
              {r.item.status === 'CONFIRMED' && r.item.owner_suspended && <SuspendedNote />}
              {r.item.status === 'CONFIRMED' && <SafetyNotice className="mt-3" />}
            </li>
          ))}

          {items.map((it) => (
            <li key={it.id} className="rounded-xl border border-gray-200 p-4">
              <div className="flex items-start justify-between gap-2">
                <h2 className="font-semibold">{it.title}</h2>
                <Badge status={it.status} type={it.type} />
              </div>
              <p className="mt-2 text-sm">
                {it.type === 'SHARE' ? (
                  <>
                    무료 나눔 · 몫 {it.filled_slots}/{it.total_slots}
                  </>
                ) : (
                  <>
                    몫 {it.filled_slots}/{it.total_slots} · 참여자 {won(it.price_per_slot)} · 내 몫{' '}
                    <b>{won(it.owner_share)}</b> · 총 {won(it.total_price)}
                  </>
                )}
              </p>
              <p className="mt-1 text-sm text-gray-500">
                {it.type === 'SHARE'
                  ? untilDate(it.deadline)
                  : `마감 ${formatDateTime(it.deadline)}`}
              </p>
              <p className="mt-3 text-sm">
                <b>신청한 사람</b>{' '}
                {it.participants.length === 0 && <span className="text-gray-500">아직 없어요</span>}
              </p>
              {it.participants.map((p) => (
                <p key={p.reservation_id} className="mt-1 flex items-center gap-2 text-sm">
                  {p.nickname}
                  {p.user_suspended && <SuspendedNote inline />}
                  <button
                    className="text-xs text-gray-400 underline"
                    onClick={() =>
                      setReporting({
                        itemId: it.id,
                        reservationId: p.reservation_id,
                        label: `참여자 ${p.nickname} (「${it.title}」)`,
                      })
                    }
                  >
                    신고
                  </button>
                </p>
              ))}
              <p className="mt-2 whitespace-pre-wrap rounded-lg bg-gray-50 p-3 text-sm">
                <b className="block">만남 장소 메모</b>
                {it.pickup_note}
              </p>
              {it.status === 'OPEN' && (
                <button
                  disabled={busyId === it.id}
                  onClick={() => setCanceling(it)}
                  className="mt-3 w-full rounded-lg border border-red-300 py-2.5 text-sm font-medium text-red-600 disabled:opacity-50"
                >
                  {busyId === it.id ? '취소하는 중…' : '모집 취소'}
                </button>
              )}
            </li>
          ))}
        </ul>
      )}

      {canceling && (
        <div
          className="fixed inset-0 z-20 flex items-end justify-center bg-black/40"
          onClick={() => setCanceling(null)}
        >
          <div
            className="w-full max-w-[430px] rounded-t-2xl bg-white p-5"
            onClick={(e) => e.stopPropagation()}
          >
            <p className="text-lg font-semibold">{canceling.title}</p>
            <p className="mt-2 text-gray-700">모집을 취소할까요?</p>
            <p className="mt-1 text-sm text-red-600">
              {canceling.participants.length > 0
                ? `이미 신청한 ${canceling.participants.length}명에게는 취소로 보여요(알림은 가지 않아요). `
                : ''}
              취소한 글은 되돌릴 수 없어요.
            </p>
            <div className="mt-5 grid grid-cols-2 gap-2">
              <button className="rounded-lg bg-gray-100 py-3" onClick={() => setCanceling(null)}>
                돌아가기
              </button>
              <button
                className="rounded-lg bg-red-600 py-3 font-semibold text-white"
                onClick={() => confirmCancel(canceling)}
              >
                모집 취소
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
