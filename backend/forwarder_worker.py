import asyncio
import re
from typing import Optional, Union, List, Dict

from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import User, Chat, Channel
from telethon.tl.custom.dialog import Dialog

from config import settings
from shared.redis_client import redis_get_json, redis_scan_json
from telegram_session import TelegramSessionManager

try:
    from solders.pubkey import Pubkey
    SOLANA_AVAILABLE = True
except ImportError:
    SOLANA_AVAILABLE = False
    print("Warning: solders not installed. Solana address validation will be disabled.")


CA_REGEX = re.compile(r"\b([1-9A-HJ-NP-Za-km-z]{32,44})\b")


def parse_chat_id(value: Union[str, int]) -> Union[str, int]:
    """Parse chat ID from string or int."""
    if isinstance(value, int):
        return value
    v = str(value).strip()
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    return v


def is_valid_solana_address(ca: str) -> bool:
    """Validate if a string is a valid Solana address."""
    if not SOLANA_AVAILABLE:
        # If solders is not available, do basic validation
        return len(ca) >= 32 and len(ca) <= 44

    try:
        Pubkey.from_string(ca)
        return True
    except Exception:
        return False


def transform_message_solana_ca(text: str) -> Optional[str]:
    """Extract and validate Solana contract address from text."""
    text = (text or "").strip()
    if not text:
        return None

    candidates = CA_REGEX.findall(text)
    for ca in candidates:
        if is_valid_solana_address(ca):
            return ca

    return None


def transform_message(text: str, transform_type: str) -> Optional[str]:
    """Transform message based on transform_type."""
    text = (text or "").strip()
    if not text:
        return None

    if transform_type == "raw":
        return text

    if transform_type == "solana_ca":
        return transform_message_solana_ca(text)

    # default fallback
    return text


async def load_default_session_str() -> str:
    """Load the default Telegram session string from Redis."""
    default = await redis_get_json("tg:session:default")
    if not default or "session_id" not in default:
        # fallback: first session
        sessions = await redis_scan_json("tg:session:sess_*")
        if not sessions:
            raise RuntimeError("No Telegram sessions found in Redis")
        session_id = sessions[0]["session_id"]
    else:
        session_id = default["session_id"]

    session = await redis_get_json(f"tg:session:{session_id}")
    if not session:
        raise RuntimeError(f"Default session {session_id} not found in Redis")

    return session["session_str"]


async def load_enabled_routes() -> List[Dict]:
    """Load all enabled routes from Redis."""
    routes = await redis_scan_json("tg:route:route_*")
    return [r for r in routes if r.get("enabled", True)]


async def resolve_route_targets(client: TelegramClient, route_configs: List[Dict]):
    """
    For each route, resolve target_chat to a proper entity (user/chat/channel)
    using dialogs, and store it as route["target_entity"].
    """
    dialogs: List[Dialog] = await client.get_dialogs(limit=None)

    for rc in route_configs:
        target = rc["target_chat"]
        target_entity = None

        if isinstance(target, int):
            # match by numeric id
            for d in dialogs:
                ent = d.entity
                if getattr(ent, "id", None) == target:
                    target_entity = ent
                    break
        else:
            # string: try username first, then title/name
            target_lower = str(target).lower()
            for d in dialogs:
                ent = d.entity
                username = getattr(ent, "username", None)
                title = getattr(ent, "title", None)
                name = (title or username or "").lower()

                if (username and target_lower == username.lower()) or target_lower == name:
                    target_entity = ent
                    break

        if not target_entity:
            print(
                f"[WARN] Could not resolve target_chat={target!r} for route {rc['route_id']}. "
                f"This route will be skipped."
            )
            rc["target_entity"] = None
        else:
            rc["target_entity"] = target_entity


async def run_forwarder():
    """Main forwarder worker loop."""
    session_str = await load_default_session_str()
    routes = await load_enabled_routes()

    if not routes:
        print("No enabled routes found. Exiting.")
        return

    manager = TelegramSessionManager(session_str=session_str)
    client = manager.create_client()

    # Build normalized route configs
    route_configs: List[Dict] = []
    source_filters: List[Union[int, str]] = []

    for r in routes:
        src = parse_chat_id(r["source_chat"])
        tgt = parse_chat_id(r["target_chat"])

        cfg = {
            "route_id": r["route_id"],
            "source_chat": src,
            "target_chat": tgt,
            "transform_type": r.get("transform_type", "solana_ca"),
        }
        route_configs.append(cfg)
        source_filters.append(src)

    @client.on(events.NewMessage(chats=source_filters))
    async def handler(event: events.NewMessage.Event):
        ent = event.chat
        src_id = getattr(ent, "id", None)
        username = getattr(ent, "username", None)

        # find matching routes for this event
        matched_routes = []
        for rc in route_configs:
            src = rc["source_chat"]

            # numeric match: use entity id (positive)
            if isinstance(src, int) and isinstance(src_id, int) and src == src_id:
                matched_routes.append(rc)

            # string match: treat as username
            elif isinstance(src, str) and username and src.lower() == username.lower():
                matched_routes.append(rc)

        if not matched_routes:
            return

        original_text = event.raw_text or ""

        for rc in matched_routes:
            new_text = transform_message(original_text, rc["transform_type"])
            if new_text is None:
                continue

            target_entity = rc.get("target_entity")
            if target_entity is None:
                continue

            try:
                await client.send_message(target_entity, new_text)
            except Exception as e:
                print(f"[ERROR] Failed to send message for route {rc['route_id']}: {repr(e)}")

    await client.start()
    me = await client.get_me()
    print(f"Forwarder running as: {me.username or me.id}")

    # Resolve target entities once using dialogs
    await resolve_route_targets(client, route_configs)

    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(run_forwarder())
