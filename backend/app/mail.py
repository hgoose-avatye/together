"""메일 발송 (기획서 5.10). 발송 방식은 이 한 함수 뒤에 숨긴다.

console: 개발용. 메일 대신 서버 콘솔에 내용을 출력한다. 운영 설정에서는 서버가 시작하지 않는다(config.check_runtime).
smtp: 운영용. 표준 라이브러리 smtplib만 쓴다. 비밀번호는 환경 변수로만 받는다.
"""

import logging
import smtplib
from email.message import EmailMessage

from app.config import settings

log = logging.getLogger("gachi.mail")


def send_mail(to: str, subject: str, body: str) -> None:
    if settings.mail_backend == "console":
        # shortcut: 개발 편의를 위해 링크 전문을 출력한다. 운영에서는 이 경로가 막혀 있다.
        print(f"\n[개발용 메일] 받는 사람: {to}\n제목: {subject}\n{body}\n", flush=True)
        return
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = settings.mail_from, to, subject
    msg.set_content(body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
        smtp.starttls()
        if settings.smtp_user:
            smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(msg)
