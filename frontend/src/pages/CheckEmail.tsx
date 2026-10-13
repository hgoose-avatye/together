import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router'
import { ApiError } from '../api'
import { resendVerification, verifyEmail } from '../endpoints'

const COOLDOWN_SECONDS = 60 // 서버의 재발송 간격(기획서 5.10, 초안 값)과 맞춘다

/** 가입 직후와, 인증이 필요한 일을 하려 할 때 오는 안내 화면. */
export default function CheckEmail() {
  const justSignedUp = (useLocation().state as { justSignedUp?: boolean } | null)?.justSignedUp
  const [wait, setWait] = useState(justSignedUp ? COOLDOWN_SECONDS : 0)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [pasted, setPasted] = useState('')
  const [checking, setChecking] = useState(false)
  const [done, setDone] = useState(false)

  useEffect(() => {
    if (wait <= 0) return
    const t = setTimeout(() => setWait((w) => w - 1), 1000)
    return () => clearTimeout(t)
  }, [wait])

  // 메일의 링크 전체나 토큰만 붙여 넣어도 된다. 링크가 다른 기기에서 열리지 않을 때를 위한 길이다.
  async function confirm() {
    const raw = pasted.trim()
    const fromLink = raw.match(/[?&]token=([^&\s#]+)/)
    const t = fromLink ? decodeURIComponent(fromLink[1]) : raw
    if (!t) return
    setChecking(true) // 누르는 즉시 비활성화해 한 번만 보낸다
    setMessage(null)
    try {
      await verifyEmail(t)
      setDone(true)
    } catch (e) {
      setMessage(e instanceof ApiError ? e.message : '서버에 연결하지 못했어요')
    } finally {
      setChecking(false)
    }
  }

  async function resend() {
    setBusy(true) // 누르는 즉시 비활성화해 중복 요청을 막는다
    setMessage(null)
    try {
      const r = await resendVerification()
      setMessage(r.sent ? '인증 메일을 다시 보냈어요' : '이미 인증된 계정이에요')
      if (r.sent) setWait(COOLDOWN_SECONDS)
    } catch (e) {
      setMessage(e instanceof ApiError ? e.message : '서버에 연결하지 못했어요')
      if (e instanceof ApiError && e.code === 'TOO_MANY_REQUESTS') setWait(COOLDOWN_SECONDS)
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="px-4 py-16 text-center">
      <h1 className="text-xl font-bold">메일을 확인해 주세요</h1>
      <p className="mt-3 text-gray-600">
        가입한 이메일로 보낸 링크를 열면 글을 올리고 몫을 신청할 수 있어요. 글 보기와 내 활동은 인증
        없이도 쓸 수 있어요.
      </p>
      <p className="mt-2 text-xs text-gray-500">
        이메일 인증은 그 메일을 쓸 수 있다는 확인일 뿐, 상대의 신원이나 안전을 보증하지 않아요.
      </p>
      <button
        disabled={busy || wait > 0}
        onClick={resend}
        className="mt-6 w-full rounded-lg bg-blue-600 py-3 font-semibold text-white disabled:opacity-50"
      >
        {wait > 0 ? `인증 메일 다시 받기 (${wait}초)` : '인증 메일 다시 받기'}
      </button>
      {done ? (
        <div role="status" className="mt-6 rounded-lg bg-green-50 p-4 text-green-800">
          <p className="font-semibold">인증이 끝났어요</p>
          <Link to="/" className="mt-2 inline-block text-sm underline">
            목록으로
          </Link>
        </div>
      ) : (
        <div className="mt-8 text-left">
          <label className="block text-sm font-medium">
            메일의 링크나 인증 코드 붙여넣기
            <input
              value={pasted}
              onChange={(e) => setPasted(e.target.value)}
              placeholder="http://…/verify?token=… 또는 토큰"
              className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2.5 text-base"
            />
          </label>
          <span className="mt-1 block text-xs text-gray-500">
            링크가 열리지 않으면(다른 기기에서 받았을 때 등) 여기에 붙여 넣어 확인할 수 있어요.
          </span>
          <button
            disabled={checking || !pasted.trim()}
            onClick={confirm}
            className="mt-3 w-full rounded-lg bg-gray-800 py-3 font-semibold text-white disabled:opacity-50"
          >
            {checking ? '확인하는 중…' : '인증 확인'}
          </button>
        </div>
      )}
      {message && (
        <p role="status" className="mt-3 text-sm text-gray-700">
          {message}
        </p>
      )}
      <Link to="/" className="mt-6 inline-block text-sm text-gray-500 underline">
        나중에 하고 목록 보기
      </Link>
    </main>
  )
}
