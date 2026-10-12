# 진행 상황 (마지막 갱신: 2026-10-12)

세션이 끊겨도 이 파일만 읽고 이어간다. 단위 작업이 끝날 때마다 갱신하고 코드와 함께 커밋한다.

## 지금 하는 일

**2단계 같이사기 API** — A-04, A-03, A-05, A-06, A-08 완료, 다음은 A-09 개설 취소
브랜치: `feat/stage-2-me` (PR #1 인증, #2 글 작성·목록, #3 몫 신청 병합됨)

## 로드맵 (단계 → 넘어가는 조건)

| 단계 | 시간 | 내용 | 넘어가는 조건 |
| --- | --- | --- | --- |
| 1 | 2–4h | 에러 형식, JWT, 인증 의존성, A-01, A-02 | 인증 테스트 통과 |
| 2 | 4–8h | A-04 글 작성 → A-03 목록(검색 q 포함) → A-05 신청 → A-06·A-08 → A-09 | API별·에러 코드별 테스트 통과 |
| 3 | 8–9h | scripts/concurrency_test.py: 10명 동시 + 같은 계정 동시 2건 | 1건 201, 9건 409 SLOTS_FULL, 같은 계정 ALREADY_JOINED, DB 건수 일치 |
| 4 | 9–14h | 화면 4개, 12h에 첫 배포(Render, SPA rewrite, CORS, gachi-prod) | 배포 URL에서 가입~신청 |
| 5 | 14–16h | 시드(동네·글·1,000건), QA 점검표 전체 | Must 완료 (태그) |
| 6 | 16–20h | 나눔 묶음(업로드→나눔 탭, 19.5h 판단), 검색 UI, 반경 | |
| 7 | 20–24h | 최종 배포, 대본, 리허설 | |

판단 시점: 8h 2단계 미완→A-09 화면 생략 / 12h 배포 실패→로컬 계속, 18h까지 데모 영상 / 16h Must 미완→Should 포기 / 19.5h 나눔 묶음 미완→통째로 제외

## 다음 할 일 (세부)

1. [2단계] A-09 취소: 조건부 UPDATE(owner_id, OPEN, 마감 전), 0행이면 재조회(404 → 403 NOT_OWNER → 409 NOT_OPEN). 무산 기록 문장은 쓰지 않는다
2. 에러 코드 14개 중 반환 조건을 테스트한 것: INVALID_INPUT, EMAIL_TAKEN, INVALID_CREDENTIALS, UNAUTHORIZED, NOT_FOUND, OWN_ITEM, ALREADY_JOINED, SLOTS_FULL, EXPIRED. 남은 것: NOT_OWNER, NOT_OPEN(A-09), FILE_TOO_LARGE, UNSUPPORTED_FILE, UPLOAD_FAILED(나눔 묶음)

## 완료

- [x] 기획서 v3.1, CLAUDE.md, 권한·포맷 훅 (8119275)
- [x] backend/frontend 기본 구조, Supabase 개발 DB 연결, 0001 마이그레이션 적용, RLS (8119275)
- [x] 기획서 v3.2: 외부 리뷰 반영(나눔 마감 다음 날 00:00, 무산 기록 범위 축소, 신청 실패 판정 순서, Must는 같이사기만)
- [x] 기획서 v3.3: 부담금 규칙(개설자도 몫 1개, 참여자 10원 단위 내림, 개설자가 나머지 부담, 상한 없음)
- [x] 1단계 공통 기반·인증: errors.py(코드 14개, 기획서 8장과 일치 테스트), security.py, deps.py, A-01, A-02. 테스트 32개 통과, 서버 기동·CORS 확인 (PR #1 병합)
- [x] 2단계 A-06 내 참여·A-08 내 글(`routers/me.py`): 성사된 글에서만 pickup_note 공개(내 글은 항상), 참여자는 한 번에 조회. 무산 기록 문장(`record_failures`): 별도 커밋, SKIP LOCKED, 실패 무시 — 잠금·실패 시나리오까지 테스트. 테스트 17개 추가
- [x] 2단계 A-05 몫 신청(`app/join.py`): 조건부 UPDATE 한 문장 + 실패 원인 판정 순서. 순차 35개 + 동시성 26개 테스트. 안전한 구현을 망가뜨리면 동시성 테스트가 실패함을 확인
- [x] 2단계 A-03 목록: 반경(Haversine)·정렬·검색(와일드카드 이스케이프)·is_joined·pickup_note 제외. 시드 1,000건 중앙값 약 85ms. 테스트 26개 추가(111개)
- [x] 2단계 A-04 글 작성(같이사기): pricing.py(부담금 규칙, 전 조합 합계 검증), geo.py(Haversine), item_schemas.py(검증), items.py(응답 변환, 표시 상태), routers/items.py. 테스트 85개 통과(17초)

## 막힌 것 / 사용자 확인 필요

- 배포용(gachi-prod) Storage 버킷 `images`는 개발용과 같은 설정으로 만들어야 함(배포 때 확인)
- 배포용 DB 연결 문자열과 Secret key는 12h 배포 때 Render 환경 변수에 직접 입력

## 준비된 외부 자원

- GitHub: https://github.com/HwangHeegu/together (origin, main 푸시됨)
- Supabase 개발용(gachi-dev, ruizsrgsebyjwxeswtwd): DB 0001 적용, Storage 버킷 `images` 확인, backend/.env 설정 완료
- Supabase 배포용(gachi-prod): 생성됨, 아직 미설정
- Render: 가입 완료

## 환경 메모

- uv, Node는 설치됨. 셸에서 안 잡히면 `export PATH="$HOME/.local/bin:$PATH"`, Node는 `source ~/.nvm/nvm.sh`
- `backend/.env`는 `uv run python scripts/setup_env.py`로 만든다(비밀번호를 대화에 붙여 넣지 않는다). 저장소 키는 `... setup_env.py storage`
- 테스트는 Supabase 개발 DB에 실제로 쓴다. 테스트 계정 이메일은 `pytest-`로 시작하고(`tests/conftest.py`의 `new_email()`), 세션 시작·종료 때 그 계정의 items·reservations까지 지운다. 새 테스트 데이터도 이 계정으로 만들 것
- 테스트 도구: `tests/conftest.py`의 `make_user(client)`는 가입+로그인을 하고 `.headers`를 준다. bcrypt가 느려(사용자 1명 ≈ 0.5초) 사용자를 공유해도 되는 테스트는 모듈 fixture(`shared_user`)를 쓴다
- pydantic은 **생략된 필드에는 검증 함수를 돌리지 않는다**. 생략 여부가 의미 있는 필드는 `Field(validate_default=True)`를 쓴다(예: ItemCreate.lng)
- 동시성 테스트(`tests/test_join_concurrency.py`)는 스레드마다 `TestClient`를 따로 만들고 `Barrier`로 같은 순간에 출발시킨다. 사용자는 `insert_user()`(가입·로그인 생략)로 만든다
- 목록 같은 위치 의존 테스트는 `tests/helpers.py`의 `unique_location()`으로 위치를 나눠 쓰고, API로 못 만드는 상태(마감 지난 글, 성사된 글)는 `insert_item()`으로 DB에 직접 넣는다
- 목록(A-03)은 페이지 나눔이 없다(기획서에 없음). 1,000건 응답이 약 327KB. 문제가 되면 상한을 두는 것을 검토
- 테스트 실행: `cd backend && uv run pytest -q` (172개, 약 50초). 빠른 확인은 파일 하나만: `uv run pytest tests/test_join.py -q` 서버: `uv run fastapi dev app/main.py`
- 편집기로 `.env`를 저장했는데 반영되지 않은 적이 있다. `.env`는 스크립트로만 고친다
