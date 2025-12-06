from pydantic import BaseModel


class StartLoginRequest(BaseModel):
    phone: str


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


class DialogModel(BaseModel):
    id: int | None
    name: str | None
    username: str | None
    type: str
