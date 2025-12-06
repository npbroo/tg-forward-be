import os
import asyncio
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession

load_dotenv()

API_ID = int(os.getenv("TG_API_ID", "0"))
API_HASH = os.getenv("TG_API_HASH")
PHONE = os.getenv("TG_PHONE")

if not API_ID or not API_HASH or not PHONE:
    raise RuntimeError("TG_API_ID, TG_API_HASH, and TG_PHONE must be set in .env")

# IMPORTANT: do NOT use a context manager that auto-starts,
# and do NOT call client.start(). That’s what prompts for phone/token.
client = TelegramClient(StringSession(), API_ID, API_HASH)


async def main():
    # Just connect; no smart login
    await client.connect()

    if not await client.is_user_authorized():
        print(f"Sending code to {PHONE}...")
        await client.send_code_request(PHONE)

        code = input("Enter the Telegram code you received: ").strip()

        # Sign in using phone + code
        await client.sign_in(PHONE, code)

    me = await client.get_me()
    print("Logged in as:", me.username or me.id)

    # Now export a proper Telethon StringSession
    session_str = client.session.save()

    print("\n================= COPY ME =================")
    print(session_str)
    print("===========================================\n")
    print("Add this to your .env as:\n")
    print(f'TG_SESSION="{session_str}"')
    print("\nTreat TG_SESSION like a private key.\n")

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
