import uuid
from datetime import datetime, timezone

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import User, Chat, Channel

from config import settings
from shared.redis_client import redis_set_json, redis_get_json, redis_scan_json
from shared.pubsub import notify_forwarder_reload


class TelegramSessionManager:
    def __init__(self, session_str: str | None = None):
        self.api_id = settings.TG_API_ID
        self.api_hash = settings.TG_API_HASH
        self.session_str = session_str

    def create_client(self) -> TelegramClient:
        if self.session_str:
            session = StringSession(self.session_str)
        else:
            session = StringSession()
        return TelegramClient(session, self.api_id, self.api_hash)


async def start_login(phone: str) -> str:
    """
    Start Telegram login: send code to phone, store temp session + phone_code_hash in Redis.
    """
    manager = TelegramSessionManager(session_str=None)
    client = manager.create_client()
    await client.connect()

    # Send login code to this phone
    result = await client.send_code_request(phone)

    # Save the in-progress session string so we can continue later
    temp_session_str = client.session.save()
    login_id = str(uuid.uuid4())

    await redis_set_json(
        f"tg:login:{login_id}",
        {
            "phone": phone,
            "session_str": temp_session_str,
            "phone_code_hash": result.phone_code_hash,  # Store phone_code_hash
        },
    )

    await client.disconnect()
    return login_id


async def confirm_login(login_id: str, code: str) -> dict:
    """
    Confirm login with the code, finalize session and store as tg:session:<session_id>.
    Returns the stored session data.
    """
    login_key = f"tg:login:{login_id}"
    login_state = await redis_get_json(login_key)
    if not login_state:
        raise ValueError("Invalid or expired login_id")

    phone = login_state["phone"]
    temp_session_str = login_state["session_str"]
    phone_code_hash = login_state["phone_code_hash"]  # Load phone_code_hash from Redis

    manager = TelegramSessionManager(session_str=temp_session_str)
    client = manager.create_client()
    await client.connect()

    # This will raise if code is invalid
    await client.sign_in(
        phone=phone,
        code=code,
        phone_code_hash=phone_code_hash,  # Pass phone_code_hash to sign_in
    )

    final_session_str = client.session.save()
    me = await client.get_me()
    await client.disconnect()

    session_id = f"sess_{uuid.uuid4().hex}"
    current_ts = datetime.now(timezone.utc).isoformat()
    session_data = {
        "session_id": session_id,
        "label": me.username or phone,
        "phone": phone,
        "session_str": final_session_str,
        "enabled": True,
        "valid": True,
        "last_error": None,
        "last_checked": current_ts,
    }

    await redis_set_json(f"tg:session:{session_id}", session_data)

    # Set this as the default session
    await redis_set_json("tg:session:default", {"session_id": session_id})

    # Notify forwarder to reload with new session
    await notify_forwarder_reload("session_created")

    return session_data


async def list_sessions() -> list[dict]:
    """
    Return all stored Telegram sessions from Redis.
    """
    return await redis_scan_json("tg:session:*")


async def mark_session_invalid(session_id: str, reason: str):
    """Mark the given session as invalid/disabled with error metadata."""
    key = f"tg:session:{session_id}"
    session = await redis_get_json(key)
    if not session:
        return

    session["enabled"] = False
    session["valid"] = False
    session["last_error"] = reason
    session["last_checked"] = datetime.now(timezone.utc).isoformat()

    await redis_set_json(key, session)


async def mark_session_checked_ok(session_id: str):
    """Refresh metadata when a session is healthy."""
    key = f"tg:session:{session_id}"
    session = await redis_get_json(key)
    if not session:
        return

    session["valid"] = True
    session.setdefault("enabled", True)
    session["last_error"] = None
    session["last_checked"] = datetime.now(timezone.utc).isoformat()

    await redis_set_json(key, session)


async def fetch_dialogs(session_str: str) -> list[dict]:
    """
    Given a stored StringSession, connect and return a list of dialogs.
    """
    manager = TelegramSessionManager(session_str=session_str)
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
