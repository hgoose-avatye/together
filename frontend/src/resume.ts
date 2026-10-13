// 이메일 인증이 필요해 중간에 인증 화면으로 갔다가 돌아올 때, 하던 일을 이어 가기 위한 기억(기획서 11장).
// 같은 브라우저에서만 이어진다(다른 기기에서 메일 링크를 열면 기본 화면으로 돌아온다).
// 저장소를 쓸 수 없는 환경에서는 조용히 건너뛴다.
const RESUME_KEY = 'gachi_resume'
const DRAFT_KEY = 'gachi_draft'
const MAX_AGE_MS = 60 * 60 * 1000 // 1시간이 지난 기억은 쓰지 않는다

export type Tab = 'GROUP_BUY' | 'SHARE'
export type Resume = { kind: 'join'; itemId: number; tab: Tab } | { kind: 'new'; path: string }

export type Draft = {
  type: Tab
  title: string
  price: string
  people: string
  deadline: string
  expiry: string
  note: string
  url: string
  photo: string | null
}

function read<T>(key: string): T | null {
  try {
    const raw = localStorage.getItem(key)
    if (!raw) return null
    const { at, value } = JSON.parse(raw) as { at: number; value: T }
    return Date.now() - at <= MAX_AGE_MS ? value : null
  } catch {
    return null
  }
}

function write(key: string, value: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify({ at: Date.now(), value }))
  } catch {
    /* 저장하지 못해도 인증 안내는 동작한다 */
  }
}

function remove(key: string) {
  try {
    localStorage.removeItem(key)
  } catch {
    /* 무시 */
  }
}

export const saveResume = (r: Resume) => write(RESUME_KEY, r)
export const peekResume = () => read<Resume>(RESUME_KEY)
export const clearResume = () => remove(RESUME_KEY)
export const saveDraft = (d: Draft) => write(DRAFT_KEY, d)
export const loadDraft = () => read<Draft>(DRAFT_KEY)
export const clearDraft = () => remove(DRAFT_KEY)

/** 인증을 마친 뒤 "계속하기" 버튼이 갈 곳과 문구. 이어서 할 일이 없으면 null. */
export function continueTarget(r: Resume | null): { to: string; label: string } | null {
  if (!r) return null
  return r.kind === 'join'
    ? { to: '/', label: '신청하던 글로 돌아가기' }
    : { to: r.path, label: '글 쓰던 곳으로 돌아가기' }
}
