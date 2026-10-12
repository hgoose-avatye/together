import { BrowserRouter, Navigate, Route, Routes } from 'react-router'
import type { ReactNode } from 'react'
import { token } from './api'
import Auth from './pages/Auth'

// 기획서 11장의 화면 4개. 각 화면은 기능을 구현하면서 채운다.
function Placeholder({ title }: { title: string }) {
  return <h1 className="p-4 text-xl font-bold">{title}</h1>
}

function RequireAuth({ children }: { children: ReactNode }) {
  return token.get() ? children : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="mx-auto min-h-dvh max-w-[430px] bg-white">
        <Routes>
          <Route path="/login" element={<Auth />} />
          <Route
            path="/"
            element={
              <RequireAuth>
                <Placeholder title="메인" />
              </RequireAuth>
            }
          />
          <Route
            path="/new"
            element={
              <RequireAuth>
                <Placeholder title="글 작성" />
              </RequireAuth>
            }
          />
          <Route
            path="/me"
            element={
              <RequireAuth>
                <Placeholder title="내 활동" />
              </RequireAuth>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    </BrowserRouter>
  )
}
