# 같이 (gachi)

@PROGRESS.md

세션을 시작하면 위 진행 상황의 "지금 하는 일"과 "다음 할 일"부터 이어간다.

자취생 공동구매·나눔 서비스. 24시간 해커톤 MVP.
**기획서 `gachi-spec.md`가 유일한 기준이다.** 구현이 기획서와 다르면 코드를 고치지 말고 먼저 사용자에게 묻는다. 기획서를 바꾸는 결정이 나면 기획서를 먼저 고치고 코드를 맞춘다.

## 구조

- `backend/` FastAPI + 동기 SQLAlchemy 2.0 + psycopg 3 + Alembic. 패키지 관리는 uv, Python 3.12
  - `app/config.py` 환경 변수, `app/db.py` 연결, `app/models.py` 테이블(기획서 7장), `app/main.py` 앱
  - `alembic/versions/` 스키마 이력. 0001이 기획서 7장 전체 스키마다
- `frontend/` React + Vite + TypeScript + react-router + Tailwind (모바일 웹, 폭 360~430px). 패키지 관리는 npm
  - `src/api.ts` 모든 API 호출이 거치는 래퍼(토큰, 401, 에러 code)
- `backend/scripts/concurrency_test.py` 실제 서버에 동시 신청 요청을 보내는 발표 시연 스크립트(`--item`, `--cleanup`은 파일 맨 위 설명 참고)
- DB는 개발 중에도 Supabase(개발용 프로젝트)에 붙는다. 로컬 Postgres는 없다.
- 핵심 SQL 3개(몫 신청, 무산 기록, 취소)는 ORM이 아니라 `text()`로 기획서 문장 그대로 쓴다.

## 명령

- 의존성 설치: `cd backend && uv sync` / `cd frontend && npm ci`
- 환경 변수: `backend/.env.example` → `backend/.env`, `frontend/.env.example` → `frontend/.env.local`
- 연결 확인: 백엔드 실행 후 `curl localhost:8000/health/db`
- 백엔드 실행: `cd backend && uv run fastapi dev app/main.py`
- 백엔드 테스트: `cd backend && uv run pytest -q`
- 마이그레이션: `cd backend && uv run alembic upgrade head` (생성은 `uv run alembic revision --autogenerate -m "..."`)
- 동시성 시연: 서버를 띄운 뒤 `cd backend && uv run python scripts/concurrency_test.py --cleanup` (pytest의 `tests/test_join_concurrency.py`와는 별개: 이쪽은 실제 HTTP)
- 시드 데이터: `cd backend && uv run python scripts/seed.py`(개발 DB를 지우고 1,000건을 새로 넣음, `--clean`으로 시드·데모 계정만 삭제). 시연 계정 `demo-owner@example.com`, `demo-guest@example.com`
- 프론트 실행: `cd frontend && npm run dev`
- 포맷: 파일 수정 시 훅이 자동으로 돌린다(Python은 ruff, 프론트는 prettier)

## 깨면 안 되는 것 (발표의 핵심)

- 몫 신청은 기획서 9.5의 조건부 UPDATE 한 문장으로만 한다. SELECT 후 UPDATE, 앱 코드에서 세기, `SELECT ... FOR UPDATE`로 바꾸지 않는다.
- 신청 가능 여부는 항상 `status = 'OPEN' AND deadline > now()`로 판단한다.
- 무산 기록 문장(5.4)은 A-06, A-08에서만, 본 처리와 **별도 트랜잭션**으로 먼저 실행한다(`SKIP LOCKED`, 실패해도 요청은 계속). 신청·목록·취소 경로에는 넣지 않는다. SQLAlchemy는 autobegin이므로 트랜잭션 블록을 두 개로 나눈다.
- 몫 신청 0행일 때 원인 판정 순서는 9.5대로 고정한다: 글 없음 → 이미 신청함 → 내 글 → 마감·무산·취소 → 몫 소진.
- `pickup_note`는 개설자와 CONFIRMED 글의 참여자에게만 응답한다. 응답 스키마를 새로 만들면 이것부터 확인한다.
- 좌표는 서버에서 소수점 2자리로 반올림한 뒤 저장한다.
- 부담금: 참여자 `price_per_slot = 10 × ⌊total_price ÷ (10 × (total_slots + 1))⌋`, 개설자 = `total_price − total_slots × price_per_slot`. 합계는 항상 총액과 같아야 한다. 개설자 부담금은 저장하지 않고 계산한다.
- 시각은 `timestamptz`이고, API는 오프셋이 붙은 ISO 문자열을 주고받는다.
- 에러 응답은 `{ "code", "message" }` 형식이고 8장 표의 code만 쓴다. 새 code가 필요하면 기획서를 먼저 고친다.
- DB 제약(UNIQUE, CHECK, FK)을 지우거나 약하게 하지 않는다.
- 클라이언트가 보낸 `owner_id`, `user_id`는 쓰지 않는다. 사용자는 항상 토큰의 `sub`로 정한다.

## 범위

- Must(F-01~F-06, F-11)는 **같이사기만** 다룬다. Must가 끝나고 동시성 테스트가 통과하기 전에는 Should(F-07~F-10)를 시작하지 않는다.
- 나눔 묶음(F-09 업로드 → F-07 나눔 탭, A-07)은 끝까지 완성하거나 통째로 뺀다. 반쪽만 넣지 않는다.
- Won't(F-12)와 제외 범위(13장)의 기능은 제안하지도 추가하지도 않는다.
- 라이브러리를 새로 추가하기 전에 묻는다(`uv add`, `npm install`은 확인 창이 뜬다). passlib은 쓰지 않는다(bcrypt 직접 사용).

## 작업 방식

- **`main`에 직접 커밋하지 않는다.** 단계마다 브랜치를 만들어 작업한다: `feat/stage-2-items`처럼 `feat/stage-N-이름`. 커밋 전에 `git branch --show-current`로 확인한다. 푸시와 PR(`main`에 합치기)은 사용자가 요청할 때만 한다.
- 단위 작업(API 하나 + 테스트)이 끝나면 `PROGRESS.md`를 갱신하고 코드와 함께 커밋한다. 세션이 끊겨도 잃는 작업이 이 단위를 넘지 않게 한다.
- 문제를 만나 해결하면 `docs/troubleshooting.md`에 **STAR(상황·과제·행동·결과)** 항목을 추가하고 해결한 커밋에 함께 넣는다. 번호는 TS-NN으로 이어 붙이고, 결과에는 확인 방법과 수치를 적는다. 확인하지 못한 것은 "미확인"이라고 쓴다.
- 결정은 대화에 남기지 않고 기획서, CLAUDE.md, PROGRESS.md 중 맞는 곳에 바로 적는다.
- API를 하나 끝낼 때마다 기획서 13장 QA 점검표의 해당 항목을 pytest로 만들어 통과시킨 뒤 완료라고 말한다.
- 몫 신청이나 무산 기록 코드를 건드리면 동시성 테스트를 다시 돌린다.
- 스키마 변경은 Alembic 마이그레이션으로만 한다. 이미 적용된 마이그레이션 파일은 고치지 않는다.
- 비밀 값(DB URL, Supabase 키, JWT secret)은 `.env`에만 두고 코드와 커밋에 넣지 않는다. 필요한 변수 이름은 `.env.example`에 적는다.
- 화면 문구는 한국어이고, 에러 문구는 기획서 8장 표를 그대로 쓴다.
- 인증이 필요한 API는 반드시 `get_current_user`를 거친다(정지 검사가 거기 있다). 토큰을 직접 해석하는 라우트를 만들지 않는다. 사용자가 부를 수 있는 정지 해제·관리 API를 만들지 않는다.
- 테스트와 시연 스크립트의 DB 변경은 `app/dbguard.py`의 `assert_dev_database` 통과가 전제다. 우회 옵션이나 허용 목록 밖의 id를 추가하지 않는다. 운영 도구 `scripts/admin.py`만 예외이고 `--yes`와 `admin_actions` 기록을 지킨다.
- 글 작성(A-04)과 몫 신청(A-05)은 `get_verified_user`를 쓴다. 인증이 필요한 라우트를 추가하면 `tests/test_email_verification.py`의 분류 표(`NEEDS_VERIFIED`/`ALLOWED_UNVERIFIED`)에 넣어 미인증 허용 여부를 정한다. 인증 토큰은 해시만 저장하고 원문을 로그·응답에 남기지 않는다(개발 console 메일 제외).
- 테스트에서 사용자를 만들 때 `insert_user`/`make_user`는 기본이 **인증된** 계정이다. 미인증이 필요하면 `verified=False`.
- 사진은 `app/uploads.py`로만 저장한다(용량 → 매직 바이트 → UUID 파일명). 테스트는 `put_object`를 바꿔 실제 Storage를 건드리지 않는다. 나눔(SHARE)의 몫·가격·마감은 서버가 정하고 클라이언트 값을 무시한다(`ItemCreate.resolve`).
- 신고(A-10)의 대상은 클라이언트가 보내지 않고 서버가 글과 신청 기록으로 정한다. 신고 접수만으로 자동 정지·숨김 같은 제재를 하지 않는다(기획서 5.9). 참여자 신고는 권한(NOT_OWNER)을 먼저 확인해 신청 기록의 존재가 새지 않게 한다.
