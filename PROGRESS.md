# 진행 상황 (마지막 갱신: 2026-10-12)

세션이 끊겨도 이 파일만 읽고 이어간다. 단위 작업이 끝날 때마다 갱신하고 코드와 함께 커밋한다.

## 지금 하는 일

**안전 묶음 PR 1~3 병합됨(#11~#13). 사용자 결정으로 PR 4(가입일·성사 횟수)와 공개 전 운영 체크리스트는 후순위.** 지금은 나눔 묶음(사진 업로드 A-07 + 나눔 작성·탭, 브랜치 `feat/share-upload`) → 시드 데이터 → 검색·반경 UI → 전체 사이클 점검 순서. 4-5 배포는 그 뒤.
화면 4개(4-0~4-4)는 병합 완료. **4-5 첫 배포는 안전 묶음(PR 1~3) 뒤로 미룬다**(사용자 결정: 배포는 당분간 하지 않고 로컬에서 확인). 이메일 인증을 넣으면 운영 메일 발송 설정이 배포 조건이 된다(기획서 5.10, 5.11).

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

1. **[안전 묶음]** 기획서 5.9~5.11, 13장 "안전 묶음 작업 순서"가 기준이다. PR마다 새 브랜치, 새 에러 코드는 구현 PR에서 기획서 8장 본표로 옮기고 `app/errors.py`와 함께 맞춘다(동기화 테스트가 검사).
   - [x] **PR 1 안전 안내 + 신고**(백엔드 테스트 232개, 프론트 build·lint 통과, 브라우저 확인은 아직): `reports` 마이그레이션(UNIQUE, CHECK), A-10, A-08 참여자에 `reservation_id`, 화면(안내 문구, 신고 버튼 3곳과 신고 창). 신고는 `OPEN`으로 쌓이기만 한다(관리 도구는 PR 2)
   - [x] **PR 2 계정 정지**(백엔드 테스트 265개, 프론트 build·lint 통과, 브라우저 확인은 아직; `verify-email`은 PR 3): `users.status` 등 컬럼, `get_current_user` 정지 검사(로그인은 비밀번호 확인 뒤), 모집 중 글 취소, A-06 `owner_suspended`·A-08 `user_suspended`, `admin.py`와 `admin_actions`, DB 보호 검증(실제 연결의 프로젝트 id를 코드의 허용 목록과 비교; pytest·테스트 도구·시연 스크립트에 적용, `admin.py`는 제외), 정지와 마지막 신청 동시성 테스트(양쪽 분기), 새 인증 라우트 우회 방지 테스트
   - [x] **PR 3 이메일 소유 확인(Should)**(백엔드 테스트 299개, 프론트 build·lint 통과, 브라우저 확인은 아직; 메일 방식은 console만 구현·SMTP는 코드만 있고 실제 발송 미확인): 해시 토큰 표, `send_mail()`(console은 운영에서 시작 거부), A-11·A-12, 미인증 제한(`EMAIL_NOT_VERIFIED`), 가입 후 안내 화면과 `/verify`, 테스트 도구(`insert_user`, `make_user`)와 시연 스크립트 갱신(약 50곳)
   - [ ] PR 4 가입일·성사 횟수 표시(Should)
2. **[4-5 배포]** 안전 묶음 뒤. 먼저 메일 발송 방식을 정한다. 사용자가 직접 할 일: Render 서비스 생성 승인, `gachi-prod` 연결 문자열·Secret key를 Render 환경 변수에 입력
3. 에러 코드 반환 조건 테스트: 나눔 묶음에서 FILE_TOO_LARGE, UNSUPPORTED_FILE, UPLOAD_FAILED까지 모두 추가
4. 화면 4개는 아직 브라우저에서 눈으로 확인하지 못했다. 로컬에서 직접 확인 필요(`uv run fastapi dev app/main.py`, `cd frontend && npm run dev`)

## 완료

- [x] 기획서 v3.1, CLAUDE.md, 권한·포맷 훅 (8119275)
- [x] backend/frontend 기본 구조, Supabase 개발 DB 연결, 0001 마이그레이션 적용, RLS (8119275)
- [x] 기획서 v3.2: 외부 리뷰 반영(나눔 마감 다음 날 00:00, 무산 기록 범위 축소, 신청 실패 판정 순서, Must는 같이사기만)
- [x] 기획서 v3.3: 부담금 규칙(개설자도 몫 1개, 참여자 10원 단위 내림, 개설자가 나머지 부담, 상한 없음)
- [x] 1단계 공통 기반·인증: errors.py(코드 14개, 기획서 8장과 일치 테스트), security.py, deps.py, A-01, A-02. 테스트 32개 통과, 서버 기동·CORS 확인 (PR #1 병합)
- [x] 3단계 동시성 시연 스크립트(`backend/scripts/concurrency_test.py`): 실제 uvicorn에 HTTP 동시 요청. 10명→성공 1·SLOTS_FULL 9(6회 연속), 몫 3개 글→정확히 3건, 같은 계정 2건→ALREADY_JOINED, DB 건수 일치. 망가뜨린 서버에서는 ✗와 종료 코드 1. TS-31
- [x] 2단계 A-09 개설 취소(`app/cancel.py`): 조건부 UPDATE 한 문장, 0행이면 글 없음→남의 글→그 밖. 신청 대 취소 경쟁에서 한쪽만 통과(20회: 신청 11 / 취소 9). 내 글 변환을 `items.to_my_items`로 공용화. 테스트 22개 추가
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
- 테스트 실행: `cd backend && uv run pytest -q` (211개, 약 60초). 빠른 확인은 파일 하나만: `uv run pytest tests/test_join.py -q` 서버: `uv run fastapi dev app/main.py`
- 편집기로 `.env`를 저장했는데 반영되지 않은 적이 있다. `.env`는 스크립트로만 고친다
