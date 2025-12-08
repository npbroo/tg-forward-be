from fastapi import APIRouter, Depends, HTTPException

from models import (
    StartLoginRequest,
    StartLoginResponse,
    ConfirmLoginRequest,
    SessionModel,
    LoginRequest,
    LoginResponse,
)
from telegram_session import start_login, confirm_login
from auth_jwt import get_current_admin, login as jwt_login
from database import get_user_by_username

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
async def auth_login(body: LoginRequest):
    """Exchange username/password for a JWT access token."""
    return await jwt_login(body)


@router.post("/start", response_model=StartLoginResponse)
async def auth_start(
    body: StartLoginRequest,
    _: str = Depends(get_current_admin),
):
    """
    Start Telegram login using the provided phone number.
    Returns login_id to be used with /auth/confirm.
    """
    if not body.phone:
        raise HTTPException(status_code=400, detail="Phone number is required")

    login_id = await start_login(body.phone)
    return StartLoginResponse(login_id=login_id)


@router.post("/confirm", response_model=SessionModel)
async def auth_confirm(
    body: ConfirmLoginRequest,
    username: str = Depends(get_current_admin),
):
    """
    Confirm Telegram login using login_id + code, store final session.
    Associates the session with the authenticated user.
    """
    # Get the current user's ID
    user = await get_user_by_username(username)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    try:
        session_data = await confirm_login(body.login_id, body.code, user_id=user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return SessionModel(
        session_id=session_data["session_id"],
        label=session_data["label"],
        phone=session_data["phone"],
        enabled=session_data.get("enabled", True),
        valid=session_data.get("valid", True),
        last_error=session_data.get("last_error"),
        last_checked=session_data.get("last_checked"),
    )


# Note: /auth/session endpoint removed - use /sessions to list all sessions for the user
