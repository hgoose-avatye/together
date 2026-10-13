import { useState } from 'react'
import { Link } from 'react-router'

/** 상단 오른쪽 사용자 아이콘. 로그인 전에는 로그인·회원가입, 로그인 후에는 내 활동·이메일 인증·로그아웃. */
export default function UserMenu({
  loggedIn,
  unverified,
  onLogout,
}: {
  loggedIn: boolean
  unverified: boolean
  onLogout: () => void
}) {
  const [open, setOpen] = useState(false)
  const item = 'block w-full px-4 py-3 text-left text-sm hover:bg-gray-50'
  return (
    <div className="relative">
      <button
        aria-label="사용자 메뉴"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="relative flex h-9 w-9 items-center justify-center rounded-full bg-gray-100"
      >
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
        {loggedIn && unverified && (
          <span
            className="absolute -top-0.5 -right-0.5 h-2.5 w-2.5 rounded-full bg-amber-500"
            aria-label="이메일 인증 필요"
          />
        )}
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-20" onClick={() => setOpen(false)} />
          <div
            role="menu"
            className="absolute right-0 z-30 mt-2 w-44 overflow-hidden rounded-xl border border-gray-200 bg-white shadow-lg"
          >
            {loggedIn ? (
              <>
                <Link role="menuitem" to="/me" className={item}>
                  내 활동
                </Link>
                {unverified && (
                  <Link role="menuitem" to="/check-email" className={`${item} text-amber-700`}>
                    이메일 인증하기
                  </Link>
                )}
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
              </>
            ) : (
              <>
                <Link role="menuitem" to="/login" className={item}>
                  로그인
                </Link>
                <Link role="menuitem" to="/login?mode=signup" className={item}>
                  회원가입
                </Link>
              </>
            )}
          </div>
        </>
      )}
    </div>
  )
}
