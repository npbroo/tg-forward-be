#!/usr/bin/env python3
"""
Test route isolation by user - verify each user only sees their own routes.
"""
import asyncio
import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent.parent.parent / "backend"
sys.path.insert(0, str(backend_dir.parent))

from backend.database import db, get_user_by_username, list_routes
from backend.auth import create_access_token, decode_jwt


async def main():
    """Test route isolation."""
    await db.connect()

    try:
        print("\n=== Testing Route Isolation ===\n")

        # Get both users
        nathan = await get_user_by_username("nathan")
        devin = await get_user_by_username("devin")

        if not nathan or not devin:
            print("ERROR: Both users 'nathan' and 'devin' must exist")
            return

        # Create JWT tokens for both users
        nathan_token = create_access_token(subject="nathan")
        devin_token = create_access_token(subject="devin")

        print(f"Nathan's user ID: {nathan.id}")
        print(f"Devin's user ID: {devin.id}")
        print()

        # Verify token contents
        nathan_payload = decode_jwt(nathan_token)
        devin_payload = decode_jwt(devin_token)

        print(f"Nathan's token subject: {nathan_payload.get('sub')}")
        print(f"Devin's token subject: {devin_payload.get('sub')}")
        print()

        # Test database queries
        print("=== Database Query Test ===\n")

        nathan_routes = await list_routes(user_id=nathan.id)
        devin_routes = await list_routes(user_id=devin.id)

        print(f"Nathan's routes (user_id={nathan.id}):")
        for route in nathan_routes:
            print(f"  - {route.routeId} | Source: {route.sourceChat} | Target: {route.targetChat}")
        if not nathan_routes:
            print("  (no routes)")
        print()

        print(f"Devin's routes (user_id={devin.id}):")
        for route in devin_routes:
            print(f"  - {route.routeId} | Source: {route.sourceChat} | Target: {route.targetChat}")
        if not devin_routes:
            print("  (no routes)")
        print()

        # Check if there's any overlap
        nathan_route_ids = {r.routeId for r in nathan_routes}
        devin_route_ids = {r.routeId for r in devin_routes}

        overlap = nathan_route_ids.intersection(devin_route_ids)

        if overlap:
            print(f"ERROR: Found overlapping routes: {overlap}")
        else:
            print("SUCCESS: No route overlap between users")

        print()
        print("=== Test Complete ===")
        print()
        print("To test via API, use these tokens:")
        print(f"\nNathan's token:\n{nathan_token[:50]}...")
        print(f"\nDevin's token:\n{devin_token[:50]}...")
        print()
        print("Test with curl:")
        print(f'\ncurl -H "Authorization: Bearer {nathan_token}" http://localhost:8001/api/routes')
        print(f'\ncurl -H "Authorization: Bearer {devin_token}" http://localhost:8001/api/routes')

    finally:
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
