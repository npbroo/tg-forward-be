#!/usr/bin/env python3
"""
Check routes in the database and verify user associations.
This helps diagnose if routes are properly isolated by user.
"""
import asyncio
import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent.parent.parent / "backend"
sys.path.insert(0, str(backend_dir.parent))

from backend.database import db, list_users, list_routes


async def main():
    """Check all routes and their user associations."""
    await db.connect()

    try:
        print("\n=== Checking Route-User Associations ===\n")

        # Get all users
        users = await list_users()
        print(f"Found {len(users)} users:")
        for user in users:
            print(f"  - {user.username} (ID: {user.id})")

        print("\n=== Routes by User ===\n")

        # Check routes for each user
        for user in users:
            routes = await list_routes(user_id=user.id)
            print(f"User: {user.username}")
            print(f"  Total routes: {len(routes)}")

            if routes:
                for route in routes:
                    print(f"    - {route.routeId}")
                    print(f"      Source: {route.sourceChat}")
                    print(f"      Target: {route.targetChat}")
                    print(f"      Enabled: {route.enabled}")
                    print(f"      UserId: {route.userId}")
                    print()
            else:
                print("    (no routes)")
            print()

        # Get ALL routes to see if any are orphaned
        all_routes = await list_routes()
        print(f"\n=== Total Routes in Database: {len(all_routes)} ===\n")

        # Check for any routes with mismatched user IDs
        user_ids = {user.id for user in users}
        orphaned = []

        for route in all_routes:
            if route.userId not in user_ids:
                orphaned.append(route)

        if orphaned:
            print(f"WARNING: Found {len(orphaned)} orphaned routes (userId doesn't match any user):")
            for route in orphaned:
                print(f"  - {route.routeId} (userId: {route.userId})")
        else:
            print("No orphaned routes found.")

    finally:
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
