from fastapi import APIRouter, Depends, HTTPException

from backend.core.models import DialogModel
from backend.services.telegram_session import fetch_dialogs
from backend.services.session_manager import SessionRegistry
from backend.auth import get_current_admin
from backend.database import get_user_by_username, db

router = APIRouter(prefix="/dialogs", tags=["dialogs"])


@router.get("", response_model=list[DialogModel])
async def get_dialogs(
    username: str = Depends(get_current_admin),
):
    """
    Get dialogs for the authenticated user's Telegram session.
    Uses the user's most recently active session.
    """
    # Get the current user
    user = await get_user_by_username(username)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    # Find the user's valid sessions
    sessions = await db.session.find_many(
        where={
            "userId": user.id,
            "enabled": True,
            "valid": True
        },
        order={"lastActivity": "desc"}
    )

    if not sessions:
        raise HTTPException(
            status_code=401,
            detail="No valid Telegram sessions found. Please login using /auth/start and /auth/confirm"
        )

    # Use the most recently active session
    session = sessions[0]

    try:
        dialogs = await fetch_dialogs(session_str=session.sessionStr)
        return [DialogModel(**d) for d in dialogs]
    except Exception as e:
        # Check if this is an authentication error that should invalidate the session
        error_str = str(e).lower()
        auth_errors = ['auth', 'authorization', 'unauthorized', 'not authorized', 'authkey']

        if any(auth_err in error_str for auth_err in auth_errors):
            # Mark session as invalid for authentication errors
            await SessionRegistry.mark_session_invalid(session.sessionId, f"Dialog fetch failed: {str(e)}")
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
