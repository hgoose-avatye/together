# 인증 메일 설정 (기획서 5.10)

서버는 `MAIL_BACKEND`로 발송 방식을 고른다. **운영(`APP_ENV=production`)에서 `console`이면 서버가 시작하지 않는다.**
`.env`는 편집기로 고치지 않고 스크립트로만 바꾼다(비밀번호는 화면에 보이지 않게 입력).

| 방식 | 명령 | 받는 곳 | 용도 |
| --- | --- | --- | --- |
| console | `uv run python scripts/setup_env.py mail console` | 서버 터미널에 링크 출력 | 빠른 개발 |
| Mailpit | `uv run python scripts/setup_env.py mail mailpit` | http://localhost:8025 (내 컴퓨터 안의 가짜 메일함) | 메일이 실제처럼 보이는지 확인 |
| Gmail | `uv run python scripts/setup_env.py mail gmail` | 실제 받은편지함 | 시연 직전 실제 수신 확인 (개발·시연 전용) |

모두 `cd backend`에서 실행하고, **바꾼 뒤 백엔드를 다시 시작**해야 적용된다.

## Mailpit (로컬)

1. 설치: `~/.local/bin/mailpit`에 바이너리를 둔다(Homebrew가 있으면 `brew install mailpit`).
2. 실행: `mailpit --listen 127.0.0.1:8025 --smtp 127.0.0.1:1025` (내 컴퓨터에서만 접근되게 127.0.0.1로 묶는다)
3. `setup_env.py mail mailpit` → 서버 재시작 → 가입하면 http://localhost:8025 에 메일이 도착한다.
4. 암호화 없는 SMTP(`SMTP_STARTTLS=false`)는 `localhost`에서만 허용된다(원격 서버로 비밀번호를 평문 전송하지 않게 서버가 시작을 거부).

pytest는 `.env`와 관계없이 메일을 `console`로 고정해 실제로 보내지 않는다. Mailpit이 떠 있으면 `tests/test_mail_smtp.py`의 실제 SMTP 전달 테스트가 함께 돈다(없으면 건너뜀).

## Gmail (실제 수신)

1. Google 계정 > 보안에서 **2단계 인증**을 켠다.
2. 같은 곳에서 **앱 비밀번호**(16자리)를 만든다. 로그인 비밀번호가 아니다.
3. `setup_env.py mail gmail` → Gmail 주소와 앱 비밀번호 입력(비밀번호는 화면에 보이지 않음. **채팅에 붙여 넣지 않는다**).
4. 서버 재시작 → 가입하면 그 Gmail로 가는 것이 아니라 **가입 폼에 적은 이메일 주소**로 간다. 받을 수 있는 실제 주소로 가입해 확인한다.
5. 한도: 하루 약 500통. 발신 주소가 개인 Gmail이므로 개발·시연까지만 쓴다(기획서 6장). 앱 비밀번호가 샜다면 Google 계정에서 즉시 폐기한다.

## 링크가 열리는 범위

메일의 링크는 `FRONTEND_URL`(기본 `http://localhost:5173`)로 만들어진다. **같은 컴퓨터의 브라우저에서만** 열린다.
휴대폰에서 열려면 같은 와이파이에서 `FRONTEND_URL`, 백엔드 `CORS_ORIGINS`, 프론트 `VITE_API_URL`을 컴퓨터의 IP로 맞추고 `npm run dev -- --host`로 띄운다.

## 배포

운영 메일 설정(SMTP 서비스 선택, `APP_ENV=production`, `MAIL_BACKEND=smtp`)과 실제 수신·인증 테스트가 끝나야 배포할 수 있다(기획서 5.11). 개인 Gmail 대신 전용 발송 서비스를 권한다.
