from datetime import UTC, datetime

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(UTC)


class UserRole(str):
    CUSTOMER = "CUSTOMER"
    ADMIN = "ADMIN"
    OPERATIONS = "OPERATIONS"


class AddressCreate(BaseModel):
    title: str = "Home"
    street: str
    city: str
    state: str
    postal_code: str
    country: str = "US"
    is_default: bool = False


class AddressResponse(AddressCreate):
    id: str
    created_at: datetime


class UserRegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=8)
    first_name: str
    last_name: str
    role: str | None = "CUSTOMER"


class UserLoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: str
    email: str
    role: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class UserProfileResponse(BaseModel):
    id: str
    email: str
    first_name: str
    last_name: str
    role: str
    is_active: bool
    addresses: list[AddressResponse] = []
    created_at: datetime
