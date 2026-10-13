"""A-07 사진 업로드 (기획서 5.6). 실제 저장소는 건드리지 않고 저장 함수를 가짜로 바꿔 검사한다."""

import re

import httpx
import pytest
from fastapi.testclient import TestClient

from app import uploads
from app.config import settings
from app.errors import AppError
from app.item_schemas import own_image_pattern

from .helpers import insert_user, unique_location

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 100
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
WEBP = b"RIFF\x24\x00\x00\x00WEBPVP8 " + b"\x00" * 100


@pytest.fixture
def stored(monkeypatch):
    calls = []
    monkeypatch.setattr(uploads, "put_object", lambda name, data, mime: calls.append((name, data, mime)))
    return calls


@pytest.fixture
def user():
    return insert_user(unique_location(), "업로더")


def upload(client, user, data: bytes, filename="a.jpg", mime="image/jpeg"):
    return client.post("/uploads", files={"file": (filename, data, mime)}, headers=user.headers)


@pytest.mark.parametrize("data, ext, mime", [(JPEG, "jpg", "image/jpeg"), (PNG, "png", "image/png"), (WEBP, "webp", "image/webp")])
def test_accepts_three_formats_and_returns_own_url(client: TestClient, user, stored, data, ext, mime):
    res = upload(client, user, data, filename="whatever.bin", mime="application/octet-stream")  # 확장자·Content-Type은 믿지 않는다
    assert res.status_code == 201, res.text
    url = res.json()["image_url"]
    assert own_image_pattern().match(url), url  # 글 작성(A-04)이 받아 주는 주소 형식과 같다
    [(name, saved, saved_mime)] = stored
    assert url.endswith(name) and name.endswith("." + ext) and saved == data and saved_mime == mime


def test_filename_is_server_generated_uuid(client: TestClient, user, stored):
    upload(client, user, JPEG, filename="../../etc/passwd.jpg")
    upload(client, user, JPEG, filename="a.jpg")
    names = [c[0] for c in stored]
    assert all(re.fullmatch(r"[0-9a-f-]{36}\.jpg", n) for n in names) and len(set(names)) == 2


def test_size_limit_boundary(client: TestClient, user, stored):
    ok = JPEG + b"\x00" * (uploads.MAX_BYTES - len(JPEG))
    assert len(ok) == 512_000 and upload(client, user, ok).status_code == 201
    big = ok + b"\x00"
    res = upload(client, user, big)
    assert (res.status_code, res.json()["code"]) == (413, "FILE_TOO_LARGE")
    assert len(stored) == 1  # 큰 파일은 저장 시도조차 하지 않는다


@pytest.mark.parametrize(
    "data, filename, mime",
    [
        (b"GIF89a" + b"\x00" * 50, "a.jpg", "image/jpeg"),  # 확장자만 jpg
        (b"<html>hi</html>", "a.png", "image/png"),
        (b"RIFF\x00\x00\x00\x00WAVEfmt ", "a.webp", "image/webp"),  # RIFF지만 WEBP가 아님
        (b"", "a.jpg", "image/jpeg"),
        (b"%PDF-1.4", "a.jpg", "image/jpeg"),
    ],
)
def test_wrong_format_is_415(client: TestClient, user, stored, data, filename, mime):
    res = upload(client, user, data, filename, mime)
    assert (res.status_code, res.json()["code"]) == (415, "UNSUPPORTED_FILE")
    assert stored == []


def test_storage_failure_is_502(client: TestClient, user, monkeypatch):
    def fail(name, data, mime):
        raise AppError("UPLOAD_FAILED")

    monkeypatch.setattr(uploads, "put_object", fail)
    res = upload(client, user, JPEG)
    assert (res.status_code, res.json()["code"]) == (502, "UPLOAD_FAILED")


class FakeResponse:
    def __init__(self, status):
        self.status_code = status


def test_put_object_maps_storage_errors(monkeypatch):
    captured = {}

    def post(url, content, headers, timeout):
        captured.update(url=url, headers=headers, content=content)
        return FakeResponse(200)

    monkeypatch.setattr(uploads.httpx, "post", post)
    uploads.put_object("x.jpg", JPEG, "image/jpeg")
    assert captured["url"].endswith(f"/storage/v1/object/{settings.supabase_bucket}/x.jpg")
    key = settings.supabase_service_key  # Secret key를 두 헤더에 넣는다
    assert captured["headers"]["apikey"] == key and captured["headers"]["Authorization"] == f"Bearer {key}"

    monkeypatch.setattr(uploads.httpx, "post", lambda *a, **k: FakeResponse(403))
    with pytest.raises(AppError) as e:
        uploads.put_object("x.jpg", JPEG, "image/jpeg")
    assert e.value.code == "UPLOAD_FAILED"

    def timeout(*a, **k):
        raise httpx.ConnectTimeout("slow")

    monkeypatch.setattr(uploads.httpx, "post", timeout)
    with pytest.raises(AppError) as e:
        uploads.put_object("x.jpg", JPEG, "image/jpeg")
    assert e.value.code == "UPLOAD_FAILED"


def test_requires_login_and_verification(client: TestClient, stored):
    assert client.post("/uploads", files={"file": ("a.jpg", JPEG, "image/jpeg")}).status_code == 401
    unverified = insert_user(unique_location(), "미인증", verified=False)
    res = upload(client, unverified, JPEG)
    assert (res.status_code, res.json()["code"]) == (403, "EMAIL_NOT_VERIFIED")
    assert stored == []


def test_missing_file_field_is_invalid_input(client: TestClient, user):
    assert client.post("/uploads", headers=user.headers).status_code == 400
