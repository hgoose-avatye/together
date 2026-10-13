import { api } from './api'
import type { Item, JoinResult, LoginResponse, MyItem, NewItem, Reservation } from './types'

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

export const listItems = (p: { type: string; sort: string; q: string }) => {
  const qs = new URLSearchParams({ type: p.type, sort: p.sort })
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
export const myItems = () => api<{ items: MyItem[] }>('/me/items')
