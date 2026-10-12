"""기획서 8장 에러 코드 기준. HTTP 상태와 화면 문구는 이 표가 유일한 출처다.

tests/test_errors.py가 이 표와 기획서 8장 표가 같은지 검사한다.
"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

# code: (HTTP 상태, 기본 화면 문구)
ERRORS: dict[str, tuple[int, str]] = {
    "INVALID_INPUT": (400, "입력값이 올바르지 않아요"),
    "EMAIL_TAKEN": (409, "이미 가입된 이메일이에요"),
    "INVALID_CREDENTIALS": (401, "이메일 또는 비밀번호가 맞지 않아요"),
    "UNAUTHORIZED": (401, "다시 로그인해 주세요"),
    "NOT_FOUND": (404, "글을 찾을 수 없어요"),
    "OWN_ITEM": (403, "내가 올린 글에는 신청할 수 없어요"),
    "NOT_OWNER": (403, "내가 올린 글만 취소할 수 있어요"),
    "ALREADY_JOINED": (409, "이미 신청한 글이에요"),
    "SLOTS_FULL": (409, "방금 몫이 모두 찼어요"),
    "NOT_OPEN": (409, "이미 끝난 글이라 취소할 수 없어요"),
    "EXPIRED": (410, "마감되었거나 취소된 글이에요"),
    "FILE_TOO_LARGE": (413, "사진이 너무 커요"),
    "UNSUPPORTED_FILE": (415, "jpg, png, webp만 올릴 수 있어요"),
    "UPLOAD_FAILED": (502, "사진을 올리지 못했어요"),
}


class AppError(Exception):
    def __init__(self, code: str, message: str | None = None, field: str | None = None):
        status, default_message = ERRORS[code]
        self.code = code
        self.status = status
        self.message = message or default_message
        self.field = field
        super().__init__(self.message)

    def body(self) -> dict:
        body = {"code": self.code, "message": self.message}
        if self.field:
            body["field"] = self.field
        return body


def invalid_input(message: str, field: str | None = None) -> AppError:
    return AppError("INVALID_INPUT", message, field)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(exc.body(), status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0]
        loc = [str(p) for p in first["loc"] if p not in ("body", "query", "path")]
        field = loc[-1] if loc else None
        msg = first.get("msg", "")
        # 우리 검증 함수가 ValueError로 던진 한국어 메시지("Value error, " 접두어)만 그대로 보여 준다.
        # 라이브러리 기본 메시지(영어)는 가리고 field만 알려 준다.
        message = (
            msg.removeprefix("Value error, ")
            if msg.startswith("Value error, ")
            else None
        )
        err = invalid_input(message or ERRORS["INVALID_INPUT"][1], field)
        return JSONResponse(err.body(), status_code=err.status)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = "NOT_FOUND" if exc.status_code == 404 else "INVALID_INPUT"
        message = "요청한 주소를 찾을 수 없어요" if exc.status_code == 404 else None
        err = AppError(code, message)
        return JSONResponse(err.body(), status_code=exc.status_code)
