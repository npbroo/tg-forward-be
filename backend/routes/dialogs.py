from fastapi import APIRouter, Depends, HTTPException

from models import DialogModel
from shared.redis_client import redis_get_json, redis_scan_json
from telegram_session import fetch_dialogs
from session_manager import SessionRegistry
from auth_jwt import get_current_admin

router = APIRouter(prefix="/dialogs", tags=["dialogs"])
@router.get("", response_model=list[DialogModel])
async def get_dialogs(
    _: str = Depends(get_current_admin),
):
    """
    Always use the default Telegram session.
    If no default is set, fall back to the first stored session.
    """
    default = await redis_get_json("tg:session:default")

    if default and "session_id" in default:
        session_id = default["session_id"]
    else:
        # Fallback: use first available session
        sessions = await redis_scan_json("tg:session:sess_*")
        if not sessions:
            raise HTTPException(
                status_code=401,
                detail="No Telegram sessions found. Please login using /auth/start and /auth/confirm"
            )
        session_id = sessions[0]["session_id"]

    session = await redis_get_json(f"tg:session:{session_id}")
    if not session:
        raise HTTPException(
            status_code=401,
            detail="Stored default session not found. Please login again using /auth/start and /auth/confirm"
        )

    if not session.get("enabled", True) or not session.get("valid", True):
        detail = session.get("last_error") or "Session is disabled or invalid. Please login again using /auth/start and /auth/confirm"
        raise HTTPException(status_code=401, detail=detail)

    try:
        dialogs = await fetch_dialogs(session_str=session["session_str"])
        return [DialogModel(**d) for d in dialogs]
    except Exception as e:
        # Check if this is an authentication error that should invalidate the session
        error_str = str(e).lower()
        auth_errors = ['auth', 'authorization', 'unauthorized', 'not authorized', 'authkey']

        if any(auth_err in error_str for auth_err in auth_errors):
            # Mark session as invalid for authentication errors
            await SessionRegistry.mark_session_invalid(session["session_id"], f"Dialog fetch failed: {str(e)}")
            raise HTTPException(
                status_code=401,
                detail=f"Session authentication failed and has been invalidated. Please login again using /auth/start and /auth/confirm. Error: {str(e)}"
            )
        else:
            # For other errors, don't mark session as invalid
            raise HTTPException(
                status_code=401,
                detail=f"Session is invalid or expired. Please login again using /auth/start and /auth/confirm. Error: {str(e)}"
            )
