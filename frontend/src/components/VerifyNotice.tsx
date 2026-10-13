/** 이메일 인증이 필요할 때 그 자리에서 보여 주는 안내와 인증 화면으로 가는 버튼. */
export default function VerifyNotice({
  message,
  onGo,
  className = '',
}: {
  message: string
  onGo: () => void
  className?: string
}) {
  return (
    <div
      role="alert"
      className={`rounded-lg bg-amber-50 px-3 py-3 text-sm text-amber-900 ${className}`}
    >
      <p>
        <b>이메일 인증이 필요해요.</b> {message}
      </p>
      <button
        type="button"
        onClick={onGo}
        className="mt-2 rounded-lg bg-amber-500 px-3 py-2 font-semibold text-white"
      >
        이메일 인증하기
      </button>
    </div>
  )
}
