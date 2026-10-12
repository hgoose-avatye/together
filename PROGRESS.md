# 진행 상황 (마지막 갱신: 2026-10-12)

세션이 끊겨도 이 파일만 읽고 이어간다. 단위 작업이 끝날 때마다 갱신하고 코드와 함께 커밋한다.

## 지금 하는 일

**2단계 같이사기 API** — A-04 완료, 다음은 A-03 목록
브랜치: `feat/stage-2-items` (1단계는 PR #1로 main에 병합됨)

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

1. [2단계] A-03 목록(검색 q, 반경, 정렬, is_mine·is_joined, pickup_note 제외) — `app/items.py`의 `to_item_out`을 재사용
2. [2단계] A-05: 0행 판정 순서(글 없음→이미 신청함→내 글→마감·무산·취소→몫 소진)
3. [2단계] A-06/A-08: 무산 기록은 별도 트랜잭션 + SKIP LOCKED, 실패 무시
4. [2단계] A-09 취소
5. 에러 코드마다 반환 조건 테스트 1개씩(전 단계에 걸쳐). 남은 코드: NOT_FOUND, OWN_ITEM, NOT_OWNER, ALREADY_JOINED, SLOTS_FULL, NOT_OPEN, EXPIRED(A-04~A-09), FILE_TOO_LARGE, UNSUPPORTED_FILE, UPLOAD_FAILED(나눔 묶음)

## 완료

- [x] 기획서 v3.1, CLAUDE.md, 권한·포맷 훅 (8119275)
- [x] backend/frontend 기본 구조, Supabase 개발 DB 연결, 0001 마이그레이션 적용, RLS (8119275)
- [x] 기획서 v3.2: 외부 리뷰 반영(나눔 마감 다음 날 00:00, 무산 기록 범위 축소, 신청 실패 판정 순서, Must는 같이사기만)
- [x] 기획서 v3.3: 부담금 규칙(개설자도 몫 1개, 참여자 10원 단위 내림, 개설자가 나머지 부담, 상한 없음)
- [x] 1단계 공통 기반·인증: errors.py(코드 14개, 기획서 8장과 일치 테스트), security.py, deps.py, A-01, A-02. 테스트 32개 통과, 서버 기동·CORS 확인 (PR #1 병합)
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
- 테스트 실행: `cd backend && uv run pytest -q` (약 17초). 서버: `uv run fastapi dev app/main.py`
- 편집기로 `.env`를 저장했는데 반영되지 않은 적이 있다. `.env`는 스크립트로만 고친다
