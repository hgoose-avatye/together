// 모든 API 호출은 이 파일을 거친다. 토큰 헤더, 401 처리, 에러 code 변환을 한곳에서 한다.

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
const TOKEN_KEY = 'gachi_token'

// 기획서 8장 에러 코드 기준
export type ErrorCode =
  | 'INVALID_INPUT'
  | 'EMAIL_TAKEN'
  | 'INVALID_CREDENTIALS'
  | 'UNAUTHORIZED'
  | 'NOT_FOUND'
  | 'OWN_ITEM'
  | 'NOT_OWNER'
  | 'ALREADY_JOINED'
  | 'SLOTS_FULL'
  | 'NOT_OPEN'
  | 'EXPIRED'
  | 'FILE_TOO_LARGE'
  | 'UNSUPPORTED_FILE'
  | 'UPLOAD_FAILED'
  | 'ALREADY_REPORTED'
  | 'ACCOUNT_SUSPENDED'
  | 'EMAIL_NOT_VERIFIED'
  | 'INVALID_TOKEN'
  | 'TOO_MANY_REQUESTS'

export class ApiError extends Error {
  readonly code: ErrorCode
  readonly status: number
  readonly field?: string

  constructor(code: ErrorCode, message: string, status: number, field?: string) {
    super(message)
    this.code = code
    this.status = status
    this.field = field
  }
}

export const token = {
  get: () => localStorage.getItem(TOKEN_KEY),
  set: (value: string) => localStorage.setItem(TOKEN_KEY, value),
  clear: () => localStorage.removeItem(TOKEN_KEY),
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  const t = token.get()
  if (t) headers.set('Authorization', `Bearer ${t}`)
  if (init.body && !(init.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }

  const res = await fetch(`${BASE_URL}${path}`, { ...init, headers })

  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    if (body.code === 'UNAUTHORIZED') {
      token.clear()
      window.location.assign('/login')
    }
    // 정지 전에 받은 토큰도 서버가 막는다. 토큰을 지우고 안내 화면으로 보낸다(로그인 중에는 그 화면이 문구를 보여 준다).
    if (body.code === 'ACCOUNT_SUSPENDED' && token.get()) {
      token.clear()
      window.location.assign('/suspended')
    }
    throw new ApiError(
      body.code ?? 'INVALID_INPUT',
      body.message ?? '요청을 처리하지 못했어요',
      res.status,
      body.field,
    )
  }
  return res.json() as Promise<T>
}
