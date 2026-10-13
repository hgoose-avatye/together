import { useState } from 'react'
import { ApiError } from '../api'
import { uploadImage } from '../endpoints'
import { shrinkImage } from '../image'

/** 사진 1장을 고르면 줄여서 바로 올리고, 올린 주소를 부모에게 알린다. */
export default function PhotoPicker({
  value,
  onChange,
  required = false,
}: {
  value: string | null
  onChange: (url: string | null) => void
  required?: boolean
}) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function pick(file: File | undefined) {
    if (!file) return
    setBusy(true)
    setError(null)
    try {
      onChange((await uploadImage(await shrinkImage(file))).image_url)
    } catch (e) {
      setError(e instanceof ApiError || e instanceof Error ? e.message : '사진을 올리지 못했어요')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      <span className="block">사진{required ? '' : ' (선택)'}</span>
      {value && (
        <img src={value} alt="올린 사진" className="mt-2 max-h-56 w-full rounded-lg object-cover" />
      )}
      <label className="mt-2 block cursor-pointer rounded-lg border border-dashed border-gray-300 px-3 py-3 text-center text-sm text-gray-600">
        {busy ? '올리는 중…' : value ? '다른 사진으로 바꾸기' : '사진 찍기 / 고르기'}
        <input
          type="file"
          accept="image/*"
          className="sr-only"
          disabled={busy}
          onChange={(e) => {
            void pick(e.target.files?.[0])
            e.target.value = '' // 같은 사진을 다시 골라도 반응하게 한다
          }}
        />
      </label>
      {value && !required && (
        <button
          type="button"
          className="mt-1 text-xs text-gray-500 underline"
          onClick={() => onChange(null)}
        >
          사진 빼기
        </button>
      )}
      {error && (
        <p role="alert" className="mt-1 text-sm text-red-600">
          {error}
        </p>
      )}
    </div>
  )
}
