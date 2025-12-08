import os
import re
from typing import Optional
from solders.pubkey import Pubkey
from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.sessions import StringSession

# --------------------------
# Load config from .env
# --------------------------
load_dotenv()

API_ID = int(os.getenv("TG_API_ID", "0"))
API_HASH = os.getenv("TG_API_HASH")
SESSION_STR = os.getenv("TG_SESSION")

SOURCE_CHAT_RAW = os.getenv("SOURCE_CHAT")   # e.g. 5073616099 or gmgnsignals
TARGET_CHAT_RAW = os.getenv("TARGET_CHAT")   # e.g. 4994190556 or mychannel

if not API_ID or not API_HASH or not SESSION_STR:
    raise RuntimeError("TG_API_ID, TG_API_HASH, and TG_SESSION must be set in .env")

if not SOURCE_CHAT_RAW or not TARGET_CHAT_RAW:
    raise RuntimeError("SOURCE_CHAT and TARGET_CHAT must be set in .env")


def parse_chat_id(value: str):
    v = value.strip()
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    return v


SOURCE_CHAT = parse_chat_id(SOURCE_CHAT_RAW)
TARGET_CHAT = parse_chat_id(TARGET_CHAT_RAW)

client = TelegramClient(StringSession(SESSION_STR), API_ID, API_HASH)

# Will hold a proper entity for the target (from channels)
TARGET_ENTITY = None


# --------------------------
# Transform / filter logic
# --------------------------

CA_REGEX = re.compile(r"\b([1-9A-HJ-NP-Za-km-z]{32,44})\b")

def is_valid_solana_address(ca: str) -> bool:
    try:
        Pubkey.from_string(ca)
        return True
    except Exception:
        return False

def transform_message(text: str) -> Optional[str]:
    text = (text or "").strip()
    if not text:
        return None

    candidates = CA_REGEX.findall(text)
    for ca in candidates:
        if is_valid_solana_address(ca):
            return ca

    return None

# --------------------------
# Event handler
# --------------------------
# Let Telethon handle source via chats=SOURCE_CHAT
@client.on(events.NewMessage(chats=SOURCE_CHAT))
async def on_new_message(event: events.NewMessage.Event):
    global TARGET_ENTITY

    original_text = event.raw_text or ""
    preview = original_text.replace("\n", " ")[:120]
    print(f"[SOURCE] {preview}...")

    new_text = transform_message(original_text)
    if new_text is None:
        print("[SKIP] Filtered out (transform_message returned None)")
        return

    await client.send_message(TARGET_ENTITY, new_text)
    print("[FORWARD] Sent transformed message to target chat")


# --------------------------
# Main entry
# --------------------------
async def main():
    global TARGET_ENTITY

    await client.connect()

    if not await client.is_user_authorized():
        raise RuntimeError("Session not authorized; check TG_SESSION.")

    me = await client.get_me()
    print("===================================")
    print(" Channel Forwarder Online")
    print(" Logged in as:", me.username or me.id)

    # Load channels once and resolve target from that list
    channels = await client.get_dialogs(limit=None)

    # Try to find target by id or username/title
    target_entity = None
    if isinstance(TARGET_CHAT, int):
        for d in channels:
            if getattr(d.entity, "id", None) == TARGET_CHAT:
                target_entity = d.entity
                break
    else:
        # string: try username first, then title
        for d in channels:
            ent = d.entity
            username = getattr(ent, "username", None)
            title = getattr(ent, "title", None)
            name = (title or username or "").lower()
            if TARGET_CHAT.lower() == (username or "").lower() or TARGET_CHAT.lower() == name:
                target_entity = ent
                break

    if not target_entity:
        raise RuntimeError(
            f"Could not resolve TARGET_CHAT={TARGET_CHAT_RAW} from channels. "
            f"Make sure this account has an open dialog with that user/channel."
        )

    TARGET_ENTITY = target_entity
    print(" Source chat:", SOURCE_CHAT_RAW)
    print(" Target chat:", TARGET_CHAT_RAW, "->", repr(TARGET_ENTITY))
    print("===================================")

    await client.run_until_disconnected()


if __name__ == "__main__":
    with client:
        client.loop.run_until_complete(main())
