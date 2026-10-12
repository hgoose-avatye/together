# 같이 (gachi)

자취생 공동구매·나눔 서비스. 24시간 해커톤 MVP.
**기획서 `gachi-spec.md`가 유일한 기준이다.** 구현이 기획서와 다르면 코드를 고치지 말고 먼저 사용자에게 묻는다. 기획서를 바꾸는 결정이 나면 기획서를 먼저 고치고 코드를 맞춘다.

## 구조

- `backend/` FastAPI + 동기 SQLAlchemy 2.0 + psycopg 3 + Alembic. 패키지 관리는 uv, Python 3.12
  - `app/config.py` 환경 변수, `app/db.py` 연결, `app/models.py` 테이블(기획서 7장), `app/main.py` 앱
  - `alembic/versions/` 스키마 이력. 0001이 기획서 7장 전체 스키마다
- `frontend/` React + Vite + TypeScript + react-router + Tailwind (모바일 웹, 폭 360~430px). 패키지 관리는 npm
  - `src/api.ts` 모든 API 호출이 거치는 래퍼(토큰, 401, 에러 code)
- `scripts/concurrency_test.py` 동시 신청 테스트 겸 발표 데모 스크립트
- DB는 개발 중에도 Supabase(개발용 프로젝트)에 붙는다. 로컬 Postgres는 없다.
- 핵심 SQL 3개(몫 신청, 무산 기록, 취소)는 ORM이 아니라 `text()`로 기획서 문장 그대로 쓴다.

## 명령

- 의존성 설치: `cd backend && uv sync` / `cd frontend && npm ci`
- 환경 변수: `backend/.env.example` → `backend/.env`, `frontend/.env.example` → `frontend/.env.local`
- 연결 확인: 백엔드 실행 후 `curl localhost:8000/health/db`
- 백엔드 실행: `cd backend && uv run fastapi dev app/main.py`
- 백엔드 테스트: `cd backend && uv run pytest -q`
- 마이그레이션: `cd backend && uv run alembic upgrade head` (생성은 `uv run alembic revision --autogenerate -m "..."`)
- 동시성 테스트: `cd backend && uv run python ../scripts/concurrency_test.py`
- 프론트 실행: `cd frontend && npm run dev`
- 포맷: 파일 수정 시 훅이 자동으로 돌린다(Python은 ruff, 프론트는 prettier)

## 깨면 안 되는 것 (발표의 핵심)

- 몫 신청은 기획서 9.5의 조건부 UPDATE 한 문장으로만 한다. SELECT 후 UPDATE, 앱 코드에서 세기, `SELECT ... FOR UPDATE`로 바꾸지 않는다.
- 신청 가능 여부는 항상 `status = 'OPEN' AND deadline > now()`로 판단한다.
- A-03, A-05, A-06, A-08, A-09는 처리 전에 무산 기록 문장(5.4)을 실행한다.
- `pickup_note`는 개설자와 CONFIRMED 글의 참여자에게만 응답한다. 응답 스키마를 새로 만들면 이것부터 확인한다.
- 좌표는 서버에서 소수점 2자리로 반올림한 뒤 저장한다.
- 시각은 `timestamptz`이고, API는 오프셋이 붙은 ISO 문자열을 주고받는다.
- 에러 응답은 `{ "code", "message" }` 형식이고 8장 표의 code만 쓴다. 새 code가 필요하면 기획서를 먼저 고친다.
- DB 제약(UNIQUE, CHECK, FK)을 지우거나 약하게 하지 않는다.
- 클라이언트가 보낸 `owner_id`, `user_id`는 쓰지 않는다. 사용자는 항상 토큰의 `sub`로 정한다.

## 범위

- Must(F-01~F-06, F-11)가 끝나고 동시성 테스트가 통과하기 전에는 Should(F-07~F-10)를 시작하지 않는다.
- Won't(F-12)와 제외 범위(13장)의 기능은 제안하지도 추가하지도 않는다.
- 라이브러리를 새로 추가하기 전에 묻는다(`uv add`, `npm install`은 확인 창이 뜬다). passlib은 쓰지 않는다(bcrypt 직접 사용).

## 작업 방식

- API를 하나 끝낼 때마다 기획서 13장 QA 점검표의 해당 항목을 pytest로 만들어 통과시킨 뒤 완료라고 말한다.
- 몫 신청이나 무산 기록 코드를 건드리면 동시성 테스트를 다시 돌린다.
- 스키마 변경은 Alembic 마이그레이션으로만 한다. 이미 적용된 마이그레이션 파일은 고치지 않는다.
- 비밀 값(DB URL, Supabase 키, JWT secret)은 `.env`에만 두고 코드와 커밋에 넣지 않는다. 필요한 변수 이름은 `.env.example`에 적는다.
- 화면 문구는 한국어이고, 에러 문구는 기획서 8장 표를 그대로 쓴다.
