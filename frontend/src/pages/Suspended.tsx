import { Link } from 'react-router'

/** 이용이 제한된 계정 안내(기획서 11장). 사유는 보여 주지 않는다. */
export default function Suspended() {
  return (
    <main className="px-4 py-20 text-center">
      <h1 className="text-xl font-bold">이용이 제한된 계정이에요</h1>
      <p className="mt-3 text-gray-600">
        운영자가 확인 중이거나 제한한 계정이에요. 이미 약속한 만남이 있다면 만나기 전에 상대와 직접
        확인해 주세요.
      </p>
      <Link to="/login" className="mt-6 inline-block rounded-lg bg-gray-100 px-4 py-2.5">
        로그인 화면으로
      </Link>
    </main>
  )
}
