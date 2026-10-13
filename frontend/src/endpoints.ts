import { api } from './api'
import type { User, Item, JoinResult, LoginResponse, MyItem, NewItem, Reservation } from './types'

const post = (body: unknown): RequestInit => ({ method: 'POST', body: JSON.stringify(body) })

export const signup = (b: {
  email: string
  password: string
  nickname: string
  lat: number
  lng: number
}) => api<{ id: number }>('/auth/signup', post(b))

export const login = (email: string, password: string) =>
  api<LoginResponse>('/auth/login', post({ email, password }))

export const uploadImage = (blob: Blob) => {
  const form = new FormData()
  form.append('file', blob, 'photo.jpg')
  return api<{ image_url: string }>('/uploads', { method: 'POST', body: form })
}

export const verifyEmail = (token: string) =>
  api<{ email_verified: boolean }>('/auth/verify-email', post({ token }))
export const resendVerification = () =>
  api<{ sent: boolean }>('/auth/resend-verification', { method: 'POST' })

export const listItems = (p: {
  type: string
  sort: string
  q: string
  radius: number
  lat?: number // 로그인 없이 둘러볼 때의 기준 위치
  lng?: number
}) => {
  const qs = new URLSearchParams({ type: p.type, sort: p.sort, radius: String(p.radius) })
  if (p.lat !== undefined && p.lng !== undefined) {
    qs.set('lat', String(p.lat))
    qs.set('lng', String(p.lng))
  }
  if (p.q.trim()) qs.set('q', p.q.trim())
  return api<{ items: Item[] }>(`/items?${qs}`)
}

export const createItem = (b: NewItem) => api<MyItem>('/items', post(b))
export const joinItem = (id: number) => api<JoinResult>(`/items/${id}/join`, { method: 'POST' })
export const cancelItem = (id: number) => api<MyItem>(`/items/${id}/cancel`, { method: 'POST' })
export const myReservations = () => api<{ reservations: Reservation[] }>('/me/reservations')
export const createReport = (b: {
  item_id: number
  reservation_id: number | null
  reason: string
  detail: string
}) => api<{ id: number; status: string }>('/reports', post(b))
export const getMe = () => api<User>('/me')
export const myItems = () => api<{ items: MyItem[] }>('/me/items')
