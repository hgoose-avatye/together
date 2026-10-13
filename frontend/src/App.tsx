import { BrowserRouter, Navigate, Route, Routes } from 'react-router'
import type { ReactNode } from 'react'
import { token } from './api'
import Auth from './pages/Auth'
import Main from './pages/Main'
import Me from './pages/Me'
import Suspended from './pages/Suspended'
import NewItem from './pages/NewItem'

function RequireAuth({ children }: { children: ReactNode }) {
  return token.get() ? children : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="mx-auto min-h-dvh max-w-[430px] bg-white">
        <Routes>
          <Route path="/login" element={<Auth />} />
          <Route path="/suspended" element={<Suspended />} />
          <Route
            path="/"
            element={
              <RequireAuth>
                <Main />
              </RequireAuth>
            }
          />
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
