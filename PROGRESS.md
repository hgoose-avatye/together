# 진행 상황 (마지막 갱신: 2026-10-12)

세션이 끊겨도 이 파일만 읽고 이어간다. 단위 작업이 끝날 때마다 갱신하고 코드와 함께 커밋한다.

## 지금 하는 일

없음. 초기 세팅 완료 후 대기.

## 다음 할 일

1. 공통 기반: 에러 응답 형식(기획서 8장), JWT 발급·검증, 인증 의존성
2. A-01 회원가입 + 테스트 (EMAIL_TAKEN, 좌표 반올림, INVALID_INPUT)
3. A-02 로그인 + 테스트 (INVALID_CREDENTIALS, 토큰 없이 호출 시 UNAUTHORIZED)
4. A-04 글 작성 → A-03 목록 → A-05 몫 신청 → A-06, A-08, A-09
5. 동시성 테스트 스크립트 (scripts/concurrency_test.py)

## 완료

- [x] 기획서 v3.1, CLAUDE.md, 권한·포맷 훅 (8119275)
- [x] backend/frontend 기본 구조, Supabase 개발 DB 연결, 0001 마이그레이션 적용, RLS (8119275)

## 막힌 것 / 사용자 확인 필요

- 원격 저장소(GitHub) 미연결. Render 배포 전에 필요
- 배포용 Supabase 프로젝트(gachi-prod) 미생성

## 환경 메모

- uv, Node는 설치됨. 셸에서 안 잡히면 `export PATH="$HOME/.local/bin:$PATH"`, Node는 `source ~/.nvm/nvm.sh`
- `backend/.env`는 `uv run python scripts/setup_env.py`로 만든다(비밀번호를 대화에 붙여 넣지 않는다)
