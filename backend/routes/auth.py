from fastapi import APIRouter, Depends, HTTPException, Header
from models import (
    StartLoginResponse,
    ConfirmLoginRequest,
    SessionModel,
)
from telegram_session import start_login, confirm_login
from shared.redis_client import redis_get_json
from config import settings

router = APIRouter(prefix="/auth", tags=["auth"])


def require_admin(x_admin_token: str = Header(..., alias="X-Admin-Token")):
    if x_admin_token != settings.ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid admin token")
    return True


@router.get("/start", response_model=StartLoginResponse)
async def auth_start(
    _: bool = Depends(require_admin),
):
    """
    Start Telegram login using the phone configured in the environment.
    Returns login_id to be used with /auth/confirm.
    """
    phone = settings.TG_PHONE

    if not phone:
        raise HTTPException(status_code=500, detail="Missing TG_PHONE configuration")

    login_id = await start_login(phone)
    return StartLoginResponse(login_id=login_id)


@router.post("/confirm", response_model=SessionModel)
async def auth_confirm(
    body: ConfirmLoginRequest,
    _: bool = Depends(require_admin),
):
    """
    Confirm Telegram login using login_id + code, store final session.
    """
    try:
        session_data = await confirm_login(body.login_id, body.code)
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


@router.get("/session", response_model=SessionModel)
async def auth_session(
    _: bool = Depends(require_admin),
):
    """
    Get the default Telegram session.
    """
    default = await redis_get_json("tg:session:default")

    if not default or "session_id" not in default:
        raise HTTPException(
            status_code=404,
            detail="No default session found. Please login using /auth/start and /auth/confirm"
        )

    session_id = default["session_id"]
    session = await redis_get_json(f"tg:session:{session_id}")

    if not session:
        raise HTTPException(
            status_code=404,
            detail="Default session not found in storage. Please login again using /auth/start and /auth/confirm"
        )

    return SessionModel(
        session_id=session["session_id"],
        label=session["label"],
        phone=session["phone"],
        enabled=session.get("enabled", True),
        valid=session.get("valid", True),
        last_error=session.get("last_error"),
        last_checked=session.get("last_checked"),
    )
