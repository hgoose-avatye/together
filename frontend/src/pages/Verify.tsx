import { useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { ApiError, token as session } from '../api'
import { verifyEmail } from '../endpoints'

type State = { kind: 'ready' } | { kind: 'busy' } | { kind: 'done' } | { kind: 'error'; message: string }

/**
 * 메일 링크가 여는 화면(/verify?token=…). 열기만 해서는 토큰을 쓰지 않고, 버튼을 눌러야 POST로 확인한다.
 * 메일 보안 검사기가 링크를 미리 열어도 토큰이 소비되지 않게 하기 위해서다(기획서 5.10).
 */
export default function Verify() {
  const t = useSearchParams()[0].get('token') ?? ''
  const [state, setState] = useState<State>({ kind: 'ready' })

  async function confirm() {
    setState({ kind: 'busy' }) // 누르는 즉시 비활성화해 한 번만 보낸다
    try {
      await verifyEmail(t)
      setState({ kind: 'done' })
    } catch (e) {
      setState({
        kind: 'error',
        message: e instanceof ApiError ? e.message : '서버에 연결하지 못했어요',
      })
    }
  }

  return (
    <main className="px-4 py-16 text-center">
      <h1 className="text-xl font-bold">이메일 인증</h1>
      {state.kind === 'done' ? (
        <>
          <p className="mt-3 text-gray-700">인증이 끝났어요.</p>
          <Link
            to={session.get() ? '/' : '/login'}
            className="mt-6 inline-block rounded-lg bg-blue-600 px-5 py-3 font-semibold text-white"
          >
            {session.get() ? '목록으로' : '로그인하러 가기'}
          </Link>
        </>
      ) : (
        <>
          <p className="mt-3 text-gray-600">아래 버튼을 눌러 이메일 인증을 완료해 주세요.</p>
          <button
            disabled={state.kind === 'busy' || !t}
            onClick={confirm}
            className="mt-6 w-full rounded-lg bg-blue-600 py-3 font-semibold text-white disabled:opacity-50"
          >
            {state.kind === 'busy' ? '확인하는 중…' : '인증 완료하기'}
          </button>
          {!t && <p className="mt-3 text-sm text-red-600">인증 링크가 올바르지 않아요</p>}
          {state.kind === 'error' && (
            <div role="alert" className="mt-3 text-sm text-red-600">
              <p>{state.message}</p>
              <Link to="/check-email" className="mt-2 inline-block underline">
                인증 메일 다시 받기
              </Link>
            </div>
          )}
        </>
      )}
    </main>
  )
}
