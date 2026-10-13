/** 오프라인 만남 안전 안내(기획서 5.9). 안전을 보장한다는 말은 쓰지 않는다. */
export default function SafetyNotice({ className = '' }: { className?: string }) {
  return (
    <p className={`rounded-lg bg-amber-50 p-3 text-xs text-amber-900 ${className}`}>
      <b>만날 때 조심하세요.</b> 사람 많은 공개된 장소에서 낮에 만나고, 불안하면 만나지 않아도
      돼요. 미리 송금하라는 요구에는 응하지 마세요. 같이는 안전을 보장하지 않아요.
    </p>
  )
}
