from typing import Optional

from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class StartLoginResponse(BaseModel):
    login_id: str


class ConfirmLoginRequest(BaseModel):
    login_id: str
    code: str


class SessionModel(BaseModel):
    session_id: str
    label: str
    phone: str
    enabled: bool
    valid: bool = True
    last_error: Optional[str] = None
    last_checked: Optional[str] = None


class DialogModel(BaseModel):
    id: int | None
    name: str | None
    username: str | None
    type: str


class RouteCreateRequest(BaseModel):
    source_chat: str | int
    target_chat: str | int
    transform_type: str = "solana_ca"  # or "raw"
    enabled: bool = True


class RouteUpdateRequest(BaseModel):
    enabled: bool | None = None
    transform_type: str | None = None
    source_chat: str | int | None = None
    target_chat: str | int | None = None


class RouteModel(BaseModel):
    route_id: str
    source_chat: str | int
    target_chat: str | int
    transform_type: str
    enabled: bool
