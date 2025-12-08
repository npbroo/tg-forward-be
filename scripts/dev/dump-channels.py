import os
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import User, Chat, Channel

# --------------------------
# Load env vars
# --------------------------
load_dotenv()

API_ID = int(os.getenv("TG_API_ID", "0"))
API_HASH = os.getenv("TG_API_HASH")
RAW_SESSION = os.getenv("TG_SESSION", "")

# Clean up quotes/whitespace just in case
SESSION_STR = RAW_SESSION.strip().strip('"').strip("'")

print("DEBUG TG_SESSION length:", len(SESSION_STR))  # you can delete later

if not API_ID or not API_HASH or not SESSION_STR:
    raise RuntimeError("TG_API_ID, TG_API_HASH, and TG_SESSION must be set in .env")

client = TelegramClient(StringSession(SESSION_STR), API_ID, API_HASH)


def classify_dialog_entity(entity) -> str:
    """
    'dm', 'bot', 'group', 'channel', 'unknown'
    """
    if isinstance(entity, User):
        if entity.bot:
            return "bot"
        return "dm"
    if isinstance(entity, Chat):
        return "group"
    if isinstance(entity, Channel):
        if entity.megagroup:
            return "group"
        return "channel"
    return "unknown"


async def main():
    await client.connect()

    if not await client.is_user_authorized():
        raise RuntimeError(
            "Session is not authorized. Check TG_SESSION; "
            "it might be invalid or expired."
        )

    me = await client.get_me()
    print("Logged in as:", me.username or me.id)

    dialogs = await client.get_dialogs(limit=None)

    lines = []
    header = "type\tname\tusername_or_phone\tid\n"
    lines.append(header)

    for d in dialogs:
        entity = d.entity
        dialog_type = classify_dialog_entity(entity)

        name = (
            getattr(entity, "title", None)
            or f"{getattr(entity, 'first_name', '')} {getattr(entity, 'last_name', '')}".strip()
            or "UNKNOWN"
        )

        username_or_phone = getattr(entity, "username", None) or getattr(entity, "phone", "") or ""
        dialog_id = entity.id

        line = f"{dialog_type}\t{name}\t{username_or_phone}\t{dialog_id}\n"
        lines.append(line)

    out_file = "scripts/dump/telegram_channels.txt"
    with open(out_file, "w", encoding="utf-8") as f:
        f.writelines(lines)

    print(f"Done. Wrote {len(dialogs)} channels to {out_file}")


if __name__ == "__main__":
    with client:
        client.loop.run_until_complete(main())
