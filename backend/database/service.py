"""
Database service layer using Prisma ORM for MySQL.
"""
from typing import Optional, List
from prisma import Prisma
from prisma.models import User, Session, Route, LoginSession

# Global Prisma client instance
db = Prisma()


async def connect_db():
    """Connect to the database."""
    if not db.is_connected():
        await db.connect()


async def disconnect_db():
    """Disconnect from the database."""
    if db.is_connected():
        await db.disconnect()


# User operations
async def get_user_by_username(username: str) -> Optional[User]:
    """Get a user by username."""
    return await db.user.find_unique(where={"username": username})


async def get_user_by_id(user_id: str) -> Optional[User]:
    """Get a user by ID."""
    return await db.user.find_unique(where={"id": user_id})


async def create_user(username: str, hashed_password: str) -> User:
    """Create a new user."""
    return await db.user.create(
        data={
            "username": username,
            "password": hashed_password
        }
    )


async def update_user_password(username: str, hashed_password: str) -> Optional[User]:
    """Update a user's password."""
    return await db.user.update(
        where={"username": username},
        data={"password": hashed_password}
    )


async def set_user_tg_account(user_id: str, tg_account: str | None) -> Optional[User]:
    """Update a user's associated Telegram account name."""
    return await db.user.update(
        where={"id": user_id},
        data={"tgAccount": tg_account}
    )


async def delete_user(username: str) -> Optional[User]:
    """Delete a user."""
    return await db.user.delete(where={"username": username})


async def list_users() -> List[User]:
    """List all users."""
    return await db.user.find_many()


# Session operations
async def get_session(session_id: str) -> Optional[Session]:
    """Get a session by session_id."""
    return await db.session.find_unique(where={"sessionId": session_id})


async def get_session_by_id(session_pk: str) -> Optional[Session]:
    """Get a session by primary key id."""
    return await db.session.find_unique(where={"id": session_pk})


async def create_session(
    session_id: str,
    session_str: str,
    label: str,
    phone: str,
    enabled: bool = True,
    valid: bool = True,
    user_id: Optional[str] = None
) -> Session:
    """Create or update a session. Each user maintains at most one session."""
    data = {
        "sessionId": session_id,
        "sessionStr": session_str,
        "label": label,
        "phone": phone,
        "enabled": enabled,
        "valid": valid,
        "version": 0,
        "userId": user_id,
    }

    if user_id:
        existing = await db.session.find_first(where={"userId": user_id})
        if existing:
            return await db.session.update(
                where={"sessionId": existing.sessionId},
                data=data
            )

    return await db.session.create(data=data)


async def update_session(session_id: str, data: dict) -> Optional[Session]:
    """Update a session by session_id."""
    return await db.session.update(
        where={"sessionId": session_id},
        data=data
    )


async def delete_session(session_id: str) -> Optional[Session]:
    """Delete a session by session_id."""
    return await db.session.delete(where={"sessionId": session_id})


async def list_sessions(enabled_only: bool = False) -> List[Session]:
    """List all sessions, optionally filtered by enabled status."""
    if enabled_only:
        return await db.session.find_many(where={"enabled": True})
    return await db.session.find_many()


async def get_valid_sessions() -> List[Session]:
    """Get all valid and enabled sessions."""
    return await db.session.find_many(
        where={"enabled": True, "valid": True}
    )


# Route operations
async def get_route(route_id: str, user_id: str | None = None) -> Optional[Route]:
    """Get a route by route_id, optionally filtered by user."""
    where: dict = {"routeId": route_id}
    if user_id:
        where["userId"] = user_id
    return await db.route.find_first(where=where)


async def create_route(
    route_id: str,
    source_chat: str,
    target_chat: str,
    transform_type: str = "solana_ca",
    enabled: bool = True,
    user_id: str | None = None,
) -> Route:
    """Create a new route."""
    if not user_id:
        raise ValueError("user_id is required to create a route")
    return await db.route.create(
        data={
            "routeId": route_id,
            "sourceChat": source_chat,
            "targetChat": target_chat,
            "transformType": transform_type,
            "enabled": enabled,
            "userId": user_id,
        }
    )


async def update_route(route_id: str, data: dict, user_id: str | None = None) -> Optional[Route]:
    """Update a route by route_id, optionally filtered by user."""
    # First verify the route exists and belongs to the user
    if user_id:
        existing = await get_route(route_id, user_id=user_id)
        if not existing:
            return None

    return await db.route.update(
        where={"routeId": route_id},
        data=data
    )


async def delete_route(route_id: str, user_id: str | None = None) -> Optional[Route]:
    """Delete a route by route_id, optionally filtered by user."""
    # First verify the route exists and belongs to the user
    if user_id:
        existing = await get_route(route_id, user_id=user_id)
        if not existing:
            return None

    return await db.route.delete(where={"routeId": route_id})


async def list_routes(enabled_only: bool = False, user_id: str | None = None) -> List[Route]:
    """List all routes, optionally filtered by enabled status and user."""
    where: dict = {}
    if enabled_only:
        where["enabled"] = True
    if user_id:
        where["userId"] = user_id
    return await db.route.find_many(where=where or None)


# LoginSession operations (for temporary Telegram login process)
async def create_login_session(login_id: str, phone: str, session_str: str, phone_code_hash: str) -> LoginSession:
    """Create a temporary login session."""
    return await db.loginsession.create(
        data={
            "loginId": login_id,
            "phone": phone,
            "sessionStr": session_str,
            "phoneCodeHash": phone_code_hash
        }
    )


async def get_login_session(login_id: str) -> Optional[LoginSession]:
    """Get a login session by login_id."""
    return await db.loginsession.find_unique(where={"loginId": login_id})


async def delete_login_session(login_id: str) -> Optional[LoginSession]:
    """Delete a login session."""
    return await db.loginsession.delete(where={"loginId": login_id})
