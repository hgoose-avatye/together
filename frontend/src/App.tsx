import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router'
import type { ReactNode } from 'react'
import { token } from './api'
import Auth from './pages/Auth'
import CheckEmail from './pages/CheckEmail'
import Main from './pages/Main'
import Me from './pages/Me'
import Suspended from './pages/Suspended'
import Verify from './pages/Verify'
import NewItem from './pages/NewItem'

// 로그인이 필요한 화면은 로그인 화면으로 보내고, 로그인하면 원래 화면으로 돌아온다(기획서 11장)
function RequireAuth({ children }: { children: ReactNode }) {
  const here = useLocation()
  const next = encodeURIComponent(here.pathname + here.search)
  return token.get() ? children : <Navigate to={`/login?next=${next}`} replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="mx-auto min-h-dvh max-w-[430px] bg-white">
        <Routes>
          <Route path="/login" element={<Auth />} />
          <Route path="/suspended" element={<Suspended />} />
          <Route path="/verify" element={<Verify />} />
          <Route
            path="/check-email"
            element={
              <RequireAuth>
                <CheckEmail />
              </RequireAuth>
            }
          />
          <Route path="/" element={<Main />} />
          <Route
            path="/new"
            element={
              <RequireAuth>
                <NewItem />
              </RequireAuth>
            }
          />
          <Route
            path="/me"
            element={
              <RequireAuth>
                <Me />
              </RequireAuth>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    </BrowserRouter>
  )
}
