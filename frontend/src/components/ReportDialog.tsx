import { useState } from 'react'
import { ApiError } from '../api'
import { createReport } from '../endpoints'

const REASONS = [
  ['INAPPROPRIATE', '부적절한 말이나 행동'],
  ['FRAUD', '사기가 의심돼요'],
  ['THREAT', '위협을 느꼈어요'],
  ['OTHER', '기타'],
] as const

export interface ReportTarget {
  itemId: number
  reservationId?: number // 없으면 글 개설자를 신고한다
  label: string
}

/** 신고 접수 창. 대상은 서버가 정하므로 사용자 id는 보내지 않는다. 접수만 하고 바로 제재되지는 않는다. */
export default function ReportDialog({
  target,
  onClose,
  onDone,
}: {
  target: ReportTarget
  onClose: () => void
  onDone: (message: string) => void
}) {
  const [reason, setReason] = useState<string>('INAPPROPRIATE')
  const [detail, setDetail] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit() {
    setBusy(true) // 누르는 즉시 비활성화해 중복 접수를 막는다
    setError(null)
    try {
      await createReport({
        item_id: target.itemId,
        reservation_id: target.reservationId ?? null,
        reason,
        detail,
      })
      onDone('신고를 접수했어요. 운영자가 확인해요')
    } catch (e) {
      if (e instanceof ApiError && e.code === 'ALREADY_REPORTED') onDone(e.message)
      else setError(e instanceof ApiError ? e.message : '서버에 연결하지 못했어요')
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 z-30 flex items-end justify-center bg-black/40" onClick={onClose}>
      <div
        className="w-full max-w-[430px] rounded-t-2xl bg-white p-5"
        onClick={(e) => e.stopPropagation()}
      >
        <p className="text-lg font-semibold">신고하기</p>
        <p className="mt-1 text-sm text-gray-600">{target.label}</p>
        <div className="mt-3 space-y-1.5">
          {REASONS.map(([value, text]) => (
            <label key={value} className="flex items-center gap-2">
              <input
                type="radio"
                name="reason"
                checked={reason === value}
                onChange={() => setReason(value)}
              />
              {text}
            </label>
          ))}
        </div>
        <textarea
          className="mt-3 w-full rounded-lg bg-gray-100 px-3 py-2.5"
          rows={3}
          maxLength={500}
          value={detail}
          onChange={(e) => setDetail(e.target.value)}
          placeholder={reason === 'OTHER' ? '내용을 적어 주세요 (필수)' : '자세한 내용 (선택)'}
        />
        <p className="mt-2 text-xs text-gray-500">
          신고는 운영자가 확인하며, 접수만으로 바로 제재되지는 않아요. 처리 결과는 알려 드리지
          못해요. 급한 위험이 있으면 112에 먼저 연락하세요.
        </p>
        {error && (
          <p role="alert" className="mt-2 text-sm text-red-600">
            {error}
          </p>
        )}
        <div className="mt-4 grid grid-cols-2 gap-2">
          <button className="rounded-lg bg-gray-100 py-3" onClick={onClose}>
            닫기
          </button>
          <button
            disabled={busy || (reason === 'OTHER' && !detail.trim())}
            className="rounded-lg bg-red-600 py-3 font-semibold text-white disabled:opacity-50"
            onClick={submit}
          >
            {busy ? '접수 중…' : '신고'}
          </button>
        </div>
      </div>
    </div>
  )
}
