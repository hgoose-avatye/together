import { useEffect, useState, type FormEvent } from 'react'
import { Navigate, useNavigate } from 'react-router'
import { ApiError, token } from '../api'
import { login, signup } from '../endpoints'
import { NEIGHBORHOODS } from '../neighborhoods'

type Loc = { lat: number; lng: number; label: string }
type Problem = { message: string; field?: string; code?: string }

export default function Auth() {
  const nav = useNavigate()
  const [mode, setMode] = useState<'login' | 'signup'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [nickname, setNickname] = useState('')
  const [loc, setLoc] = useState<Loc | null>(null)
  // 위치 API가 없는 브라우저는 처음부터 동네 목록을 보여 준다
  const [pickList, setPickList] = useState(() => !('geolocation' in navigator))
  const [problem, setProblem] = useState<Problem | null>(null)
  const [busy, setBusy] = useState(false)

  // 가입 탭을 열면 브라우저 위치를 먼저 요청하고, 거부하거나 실패하면 동네 목록으로 넘어간다(기획서 11장).
  useEffect(() => {
    if (mode !== 'signup' || loc || pickList) return
    navigator.geolocation.getCurrentPosition(
      (p) => setLoc({ lat: p.coords.latitude, lng: p.coords.longitude, label: '현재 위치' }),
      () => setPickList(true),
      { timeout: 8000 },
    )
  }, [mode, loc, pickList])

  if (token.get()) return <Navigate to="/" replace />

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (busy) return
    setProblem(null)
    setBusy(true)
    try {
      if (mode === 'signup') {
        if (!loc) {
          setProblem({ message: '동네를 선택해 주세요', field: 'location' })
          return
        }
        await signup({ email, password, nickname, lat: loc.lat, lng: loc.lng })
      }
      token.set((await login(email, password)).access_token) // 가입에 성공하면 이어서 자동 로그인
      // 가입 직후에는 메일 확인 안내 화면으로. 로그인만 한 경우는 목록으로(미인증이어도 둘러볼 수 있다).
      nav(mode === 'signup' ? '/check-email' : '/', {
        replace: true,
        state: { justSignedUp: mode === 'signup' },
      })
    } catch (err) {
      if (err instanceof ApiError) {
        setProblem({ message: err.message, field: err.field, code: err.code })
        if (err.code === 'INVALID_CREDENTIALS') setPassword('')
      } else {
        setProblem({ message: '서버에 연결하지 못했어요. 잠시 뒤 다시 시도해 주세요' })
      }
    } finally {
      setBusy(false)
    }
  }

  const fieldError = (name: string) =>
    problem?.field === name ? <p className="mt-1 text-sm text-red-600">{problem.message}</p> : null
  const input = 'mt-1 w-full rounded-lg border border-gray-300 px-3 py-2.5 text-base'

  return (
    <main className="px-4 py-10">
      <h1 className="text-3xl font-bold">같이</h1>
      <p className="mt-1 text-gray-600">이웃과 같이 사고, 남은 건 나눠요</p>

      <div className="mt-8 grid grid-cols-2 rounded-lg bg-gray-100 p-1 text-center">
        {(['login', 'signup'] as const).map((m) => (
          <button
            key={m}
            type="button"
            onClick={() => {
              setMode(m)
              setProblem(null)
            }}
            className={`rounded-md py-2 font-medium ${mode === m ? 'bg-white shadow' : 'text-gray-500'}`}
          >
            {m === 'login' ? '로그인' : '가입'}
          </button>
        ))}
      </div>

      <form onSubmit={submit} className="mt-6 space-y-4">
        <label className="block">
          이메일
          <input
            className={input}
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          {fieldError('email')}
        </label>
        <label className="block">
          비밀번호
          <input
            className={input}
            type="password"
            required
            minLength={8}
            autoComplete={mode === 'signup' ? 'new-password' : 'current-password'}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          {fieldError('password')}
        </label>

        {mode === 'signup' && (
          <>
            <label className="block">
              닉네임
              <input
                className={input}
                required
                minLength={2}
                maxLength={20}
                value={nickname}
                onChange={(e) => setNickname(e.target.value)}
              />
              {fieldError('nickname')}
            </label>
            <div>
              내 동네
              {loc ? (
                <p className="mt-1 flex items-center justify-between rounded-lg bg-gray-50 px-3 py-2.5">
                  <span>{loc.label}</span>
                  <button
                    type="button"
                    className="text-sm text-blue-600"
                    onClick={() => {
                      setLoc(null)
                      setPickList(true)
                    }}
                  >
                    동네에서 고르기
                  </button>
                </p>
              ) : pickList ? (
                <select
                  className={input}
                  defaultValue=""
                  onChange={(e) => {
                    const n = NEIGHBORHOODS.find((x) => x.name === e.target.value)
                    if (n) setLoc({ lat: n.lat, lng: n.lng, label: n.name })
                  }}
                >
                  <option value="" disabled>
                    동네를 선택해 주세요
                  </option>
                  {NEIGHBORHOODS.map((n) => (
                    <option key={n.name}>{n.name}</option>
                  ))}
                </select>
              ) : (
                <p className="mt-1 text-gray-500">위치를 확인하는 중이에요…</p>
              )}
              <p className="mt-1 text-xs text-gray-500">
                정확한 위치는 저장하지 않고 약 1km 단위로만 저장해요.
              </p>
              {fieldError('location')}
              {fieldError('lat')}
            </div>
          </>
        )}

        {problem && !problem.field && (
          <p className="text-sm text-red-600" role="alert">
            {problem.message}
            {problem.code === 'EMAIL_TAKEN' && (
              <button
                type="button"
                className="ml-2 underline"
                onClick={() => {
                  setMode('login')
                  setProblem(null)
                }}
              >
                로그인하기
              </button>
            )}
          </p>
        )}

        <button
          disabled={busy}
          className="w-full rounded-lg bg-blue-600 py-3 font-semibold text-white disabled:opacity-50"
        >
          {busy ? '잠시만요…' : mode === 'login' ? '로그인' : '가입하고 시작하기'}
        </button>
      </form>
    </main>
  )
}
