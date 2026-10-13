"""A-07 사진 업로드 (기획서 5.6). 형식은 파일 앞부분의 시그니처로 판단하고, 파일명은 서버가 만든 UUID를 쓴다.

저장은 Supabase Storage REST를 Secret key로 호출한다(Publishable key는 쓰지 않는다).
"""

import uuid

import httpx

from app.config import settings
from app.errors import AppError

MAX_BYTES = 500 * 1024  # 512,000바이트. 버킷의 크기 제한과 같은 값
TIMEOUT_SECONDS = 15


def detect_type(head: bytes) -> tuple[str, str] | None:
    """(확장자, MIME)을 돌려준다. jpeg, png, webp가 아니면 None. 확장자와 Content-Type은 믿지 않는다."""
    if head.startswith(b"\xff\xd8\xff"):
        return "jpg", "image/jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png", "image/png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp", "image/webp"
    return None


def put_object(name: str, data: bytes, mime: str) -> None:
    """버킷에 올린다. 실패하면 UPLOAD_FAILED. 테스트는 이 함수를 바꿔 실제 저장소를 건드리지 않는다."""
    if not (settings.supabase_url and settings.supabase_service_key):
        raise AppError("UPLOAD_FAILED")
    url = f"{settings.supabase_url.rstrip('/')}/storage/v1/object/{settings.supabase_bucket}/{name}"
    headers = {
        "apikey": settings.supabase_service_key,
        "Authorization": f"Bearer {settings.supabase_service_key}",
        "Content-Type": mime,
        "x-upsert": "false",
    }
    try:
        res = httpx.post(url, content=data, headers=headers, timeout=TIMEOUT_SECONDS)
    except httpx.HTTPError as e:
        raise AppError("UPLOAD_FAILED") from e
    if res.status_code not in (200, 201):
        raise AppError("UPLOAD_FAILED")


def public_url(name: str) -> str:
    return f"{settings.supabase_url.rstrip('/')}/storage/v1/object/public/{settings.supabase_bucket}/{name}"


def store_image(data: bytes) -> str:
    """검증하고 저장한 뒤 공개 주소를 돌려준다. 순서: 용량 → 형식 → 저장."""
    if len(data) > MAX_BYTES:
        raise AppError("FILE_TOO_LARGE")
    kind = detect_type(data[:12])
    if kind is None:
        raise AppError("UNSUPPORTED_FILE")
    ext, mime = kind
    name = f"{uuid.uuid4()}.{ext}"
    put_object(name, data, mime)
    return public_url(name)
