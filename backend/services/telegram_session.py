"""
Enhanced Telegram session management with versioning and improved error handling.
"""
import uuid
from datetime import datetime, timezone

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import User, Chat, Channel

from backend.core.config import settings
from backend.services.session_manager import EnhancedSessionManager, SessionRegistry
from backend.database import create_session


async def start_login(phone: str) -> str:
    """
    Start Telegram login: send code to phone, store temp session + phone_code_hash in database.
    """
    from backend.database import create_login_session

    manager = EnhancedSessionManager(session_str=None)
    client = manager.create_client()
    await client.connect()

    # Send login code to this phone
    result = await client.send_code_request(phone)

    # Save the in-progress session string so we can continue later
    temp_session_str = client.session.save()
    login_id = str(uuid.uuid4())

    # Store in database
    await create_login_session(
        login_id=login_id,
        phone=phone,
        session_str=temp_session_str,
        phone_code_hash=result.phone_code_hash
    )

    await client.disconnect()
    return login_id


async def confirm_login(login_id: str, code: str, user_id: str = None) -> dict:
    """
    Confirm login with the code, finalize session and store in database.
    Returns the stored session data.
    """
    from backend.database import get_login_session, delete_login_session
    from backend.services.events import emit_session_created

    login_state = await get_login_session(login_id)
    if not login_state:
        raise ValueError("Invalid or expired login_id")

    phone = login_state.phone
    temp_session_str = login_state.sessionStr
    phone_code_hash = login_state.phoneCodeHash

    manager = EnhancedSessionManager(session_str=temp_session_str)
    client = manager.create_client()
    await client.connect()

    # This will raise if code is invalid
    await client.sign_in(
        phone=phone,
        code=code,
        phone_code_hash=phone_code_hash,
    )

    final_session_str = client.session.save()
    me = await client.get_me()
    await client.disconnect()

    session_id = f"sess_{uuid.uuid4().hex}"
    label = me.username or phone

    # Save to MySQL database
    session = await create_session(
        session_id=session_id,
        session_str=final_session_str,
        label=label,
        phone=phone,
        enabled=True,
        valid=True,
        user_id=user_id
    )

    # Clean up the temporary login session
    await delete_login_session(login_id)

    # Emit session created event for the user's worker
    if user_id:
        await emit_session_created(user_id)

    # Return session data
    current_ts = datetime.now(timezone.utc).isoformat()
    session_data = {
        "session_id": session_id,
        "label": label,
        "phone": phone,
        "session_str": final_session_str,
        "enabled": True,
        "valid": True,
        "last_error": None,
        "last_checked": current_ts,
        "version": 1,
    }

    return session_data


async def list_sessions() -> list[dict]:
    """
    Return all stored Telegram sessions from database.
    """
    from backend.database import list_sessions as db_list_sessions

    sessions = await db_list_sessions()
    return [
        {
            "session_id": s.sessionId,
            "label": s.label,
            "phone": s.phone,
            "enabled": s.enabled,
            "valid": s.valid,
            "last_error": s.lastError,
            "last_checked": s.lastChecked.isoformat() if s.lastChecked else None,
            "version": s.version
        }
        for s in sessions
    ]


# For backward compatibility, maintain the original functions
async def mark_session_invalid(session_id: str, reason: str):
    """Legacy function for backward compatibility."""
    await SessionRegistry.mark_session_invalid(session_id, reason)


async def mark_session_checked_ok(session_id: str):
    """Legacy function for backward compatibility."""
    await SessionRegistry.mark_session_checked_ok(session_id)


async def fetch_dialogs(session_str: str) -> list[dict]:
    """
    Given a stored StringSession, connect and return a list of dialogs.
    """
    manager = EnhancedSessionManager(session_str=session_str)
    client = manager.create_client()
    await client.connect()

    dialogs = await client.get_dialogs(limit=None)
    out: list[dict] = []

    for d in dialogs:
        ent = d.entity

        if isinstance(ent, User):
            d_type = "User"
        elif isinstance(ent, Chat):
            d_type = "Chat"
        elif isinstance(ent, Channel):
            d_type = "Channel"
        else:
            d_type = ent.__class__.__name__

        name = (
            getattr(ent, "title", None)
            or f"{getattr(ent, 'first_name', '')} {getattr(ent, 'last_name', '')}".strip()
            or None
        )

        out.append(
            {
                "id": getattr(ent, "id", None),
                "name": name,
                "username": getattr(ent, "username", None),
                "type": d_type,
            }
        )

    await client.disconnect()
    return out
