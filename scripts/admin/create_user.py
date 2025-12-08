"""
Script to create an initial admin user in the database.
Run this after setting up the database to create your first user.
"""
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.database import connect_db, disconnect_db, create_user, get_user_by_username
from backend.auth.password import hash_password


async def main():
    await connect_db()

    # Get username and password from command line or use defaults
    if len(sys.argv) >= 3:
        username = sys.argv[1]
        password = sys.argv[2]
    else:
        print("Usage: python create_initial_user.py <username> <password>")
        print("\nExiting...")
        return

    # Check if user already exists
    existing = await get_user_by_username(username)
    if existing:
        print(f"❌ User '{username}' already exists!")
        await disconnect_db()
        return

    # Create the user
    hashed_password = hash_password(password)
    user = await create_user(username, hashed_password)

    print(f"✅ User created successfully!")
    print(f"   Username: {user.username}")
    print(f"   ID: {user.id}")
    print(f"   Created: {user.createdAt}")

    await disconnect_db()


if __name__ == "__main__":
    asyncio.run(main())
