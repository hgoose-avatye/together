import { useState } from 'react'
import { Link } from 'react-router'

const Icon = () => (
  <svg
    viewBox="0 0 24 24"
    className="h-5 w-5"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    aria-hidden="true"
  >
    <circle cx="12" cy="8" r="4" />
    <path d="M4 21c0-4 4-6 8-6s8 2 8 6" strokeLinecap="round" />
  </svg>
)
const button = 'flex h-9 w-9 items-center justify-center rounded-full bg-gray-100'

/**
 * 상단 오른쪽 사용자 아이콘.
 * 로그인 전에는 메뉴 없이 누르면 바로 로그인 화면으로 간다(가입은 로그인 화면의 가입 탭).
 * 로그인 후에는 내 활동과 로그아웃만 있는 메뉴가 열린다. 이메일 인증 안내는 메인 상단 띠가 맡는다.
 */
export default function UserMenu({
  loggedIn,
  onLogout,
}: {
  loggedIn: boolean
  onLogout: () => void
}) {
  const [open, setOpen] = useState(false)

  if (!loggedIn) {
    return (
      <Link to="/login" aria-label="로그인" className={button}>
        <Icon />
      </Link>
    )
  }

  const item = 'block w-full px-4 py-3 text-left text-sm hover:bg-gray-50'
  return (
    <div className="relative">
      <button
        aria-label="사용자 메뉴"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className={button}
      >
        <Icon />
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-20" onClick={() => setOpen(false)} />
          <div
            role="menu"
            className="absolute right-0 z-30 mt-2 w-40 overflow-hidden rounded-xl border border-gray-200 bg-white shadow-lg"
          >
            <Link role="menuitem" to="/me" className={item}>
              내 활동
            </Link>
            <button
              role="menuitem"
              className={`${item} text-gray-500`}
              onClick={() => {
                setOpen(false)
                onLogout()
              }}
            >
              로그아웃
            </button>
          </div>
        </>
      )}
    </div>
  )
}
