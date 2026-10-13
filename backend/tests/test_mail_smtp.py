"""SMTP 발송 경로 (기획서 5.10). 가짜 SMTP로 호출을 검사하고, 로컬 Mailpit이 떠 있으면 실제로 보내 받아 본다."""

import uuid

import httpx
import pytest

from app import mail
from app.config import check_runtime
from app.mail import send_mail

from .test_email_verification import settings as make_settings

MAILPIT_API = "http://127.0.0.1:8025/api/v1"


class FakeSMTP:
    instances = []

    def __init__(self, host, port, timeout):
        self.host, self.port, self.timeout, self.calls, self.sent = host, port, timeout, [], None
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def starttls(self):
        self.calls.append("starttls")

    def login(self, user, password):
        self.calls.append(("login", user, password))

    def send_message(self, msg):
        self.calls.append("send")
        self.sent = msg


@pytest.fixture
def fake(monkeypatch):
    FakeSMTP.instances.clear()
    monkeypatch.setattr(mail.smtplib, "SMTP", FakeSMTP)
    for k, v in dict(mail_backend="smtp", smtp_host="smtp.example.com", smtp_port=587, smtp_user="u@gmail.com", smtp_password="pw", mail_from="u@gmail.com", smtp_starttls=True).items():
        monkeypatch.setattr(mail.settings, k, v)
    return FakeSMTP


def test_smtp_uses_tls_before_login(fake):
    send_mail("to@example.com", "제목", "본문")
    [s] = fake.instances
    assert (s.host, s.port) == ("smtp.example.com", 587)
    assert s.calls == ["starttls", ("login", "u@gmail.com", "pw"), "send"]  # 로그인 전에 암호화한다
    assert (s.sent["To"], s.sent["From"], s.sent["Subject"]) == ("to@example.com", "u@gmail.com", "제목")


def test_smtp_without_tls_and_login_for_local_server(fake, monkeypatch):
    monkeypatch.setattr(mail.settings, "smtp_starttls", False)
    monkeypatch.setattr(mail.settings, "smtp_user", "")
    send_mail("to@example.com", "s", "b")
    assert fake.instances[0].calls == ["send"]


def test_unencrypted_login_is_refused_for_remote_hosts():
    # 비밀번호를 평문으로 보내는 설정은 로컬 서버에서만 허용한다
    with pytest.raises(RuntimeError, match="localhost"):
        check_runtime(make_settings(mail_backend="smtp", smtp_host="smtp.gmail.com", mail_from="a@gmail.com", smtp_starttls=False))
    check_runtime(make_settings(mail_backend="smtp", smtp_host="localhost", mail_from="a@b.c", smtp_starttls=False))


def mailpit_up() -> bool:
    try:
        return httpx.get(f"{MAILPIT_API}/info", timeout=1).status_code == 200
    except httpx.HTTPError:
        return False


@pytest.mark.skipif(not mailpit_up(), reason="로컬 Mailpit(127.0.0.1:8025)이 떠 있지 않음")
def test_real_delivery_to_local_mailpit(monkeypatch):
    """실제 SMTP 통신: 한글 보낸 사람 이름과 본문이 그대로 도착하는지."""
    for k, v in dict(mail_backend="smtp", smtp_host="127.0.0.1", smtp_port=1025, smtp_starttls=False, smtp_user="", smtp_password="", mail_from="같이 <no-reply@gachi.local>").items():
        monkeypatch.setattr(mail.settings, k, v)
    marker = f"pytest-mailpit-{uuid.uuid4().hex[:8]}@example.com"
    send_mail(marker, "[같이] 이메일 인증을 완료해 주세요", "링크: http://localhost:5173/verify?token=abc")
    found = httpx.get(f"{MAILPIT_API}/search", params={"query": f"to:{marker}"}, timeout=5).json()
    assert found["messages_count"] == 1, found
    msg = httpx.get(f"{MAILPIT_API}/message/{found['messages'][0]['ID']}", timeout=5).json()
    assert msg["Subject"] == "[같이] 이메일 인증을 완료해 주세요"
    assert msg["From"]["Name"] == "같이" and msg["From"]["Address"] == "no-reply@gachi.local"
    assert "verify?token=abc" in msg["Text"]
    httpx.request("DELETE", f"{MAILPIT_API}/messages", json={"IDs": [found["messages"][0]["ID"]]}, timeout=5)  # 내가 보낸 메일만 지운다
