// 기획서 10장 API 응답. 서버의 pydantic 스키마(backend/app/item_schemas.py, schemas.py)와 같다.

export type ItemStatus = 'OPEN' | 'CONFIRMED' | 'FAILED' | 'CANCELED'

export interface User {
  id: number
  nickname: string
  lat: number
  lng: number
}

export interface LoginResponse {
  access_token: string
  token_type: string
  expires_in: number
  user: User
}

/** 목록(A-03) 항목. pickup_note는 없다. */
export interface Item {
  id: number
  type: 'GROUP_BUY' | 'SHARE'
  category: string
  title: string
  owner_nickname: string
  total_slots: number
  filled_slots: number
  remaining_slots: number
  total_price: number
  price_per_slot: number
  deadline: string
  distance_km: number
  status: ItemStatus
  is_mine: boolean
  is_joined: boolean
  image_url: string | null
  product_url: string | null
}

export interface JoinResult {
  reservation_id: number
  item_id: number
  filled_slots: number
  total_slots: number
  remaining_slots: number
  status: ItemStatus
}

export interface Reservation {
  reservation_id: number
  joined_at: string
  item: {
    id: number
    type: string
    title: string
    owner_nickname: string
    price_per_slot: number
    deadline: string
    status: ItemStatus
    pickup_note: string | null // 성사(CONFIRMED)된 글에서만 값이 있다
    owner_suspended: boolean
  }
}

export interface MyItem {
  id: number
  type: string
  title: string
  filled_slots: number
  total_slots: number
  total_price: number
  price_per_slot: number
  owner_share: number
  deadline: string
  status: ItemStatus
  pickup_note: string
  participants: {
    reservation_id: number
    nickname: string
    joined_at: string
    user_suspended: boolean
  }[]
}

export interface NewItem {
  type: 'GROUP_BUY'
  title: string
  total_slots: number // 이웃에게 나눌 몫 = 나 포함 인원 - 1
  total_price: number
  deadline: string // 오프셋이 붙은 ISO 문자열
  pickup_note: string
  product_url?: string
}
