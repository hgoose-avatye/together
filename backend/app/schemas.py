from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel, EmailStr, field_validator

from app.security import MAX_PASSWORD_BYTES


def round_coord(value: float | Decimal) -> Decimal:
    """좌표를 소수점 2자리(약 1km 격자)로 반올림한다. float 오차를 피하려고 문자열을 거친다."""
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    nickname: str
    lat: float
    lng: float

    @field_validator("email")
    @classmethod
    def lower_email(cls, v: str) -> str:
        return v.lower()

    @field_validator("password")
    @classmethod
    def check_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("비밀번호는 8자 이상이어야 해요")
        if len(v.encode()) > MAX_PASSWORD_BYTES:
            raise ValueError("비밀번호가 너무 길어요")
        return v

    @field_validator("nickname")
    @classmethod
    def check_nickname(cls, v: str) -> str:
        v = v.strip()
        if not 2 <= len(v) <= 20:
            raise ValueError("닉네임은 2~20자로 입력해 주세요")
        return v

    @field_validator("lat")
    @classmethod
    def check_lat(cls, v: float) -> float:
        if not -90 <= v <= 90:
            raise ValueError("위도가 올바르지 않아요")
        return v

    @field_validator("lng")
    @classmethod
    def check_lng(cls, v: float) -> float:
        if not -180 <= v <= 180:
            raise ValueError("경도가 올바르지 않아요")
        return v


class SignupResponse(BaseModel):
    id: int


class LoginRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email")
    @classmethod
    def lower_email(cls, v: str) -> str:
        return v.lower()


class UserOut(BaseModel):
    id: int
    nickname: str
    lat: float
    lng: float
    email_verified: bool = False


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


class VerifyEmailRequest(BaseModel):
    token: str


class VerifyEmailResponse(BaseModel):
    email_verified: bool


class ResendResponse(BaseModel):
    sent: bool
