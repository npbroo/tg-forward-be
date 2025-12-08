"""
Database service layer using Prisma ORM for MySQL.
"""
from typing import Optional, List
from prisma import Prisma
from prisma.models import User, Session, Route, DefaultSession

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


async def get_session_by_id(id: str) -> Optional[Session]:
    """Get a session by primary key id."""
    return await db.session.find_unique(where={"id": id})


async def create_session(
    session_id: str,
    session_str: str,
    label: str,
    phone: str,
    enabled: bool = True,
    valid: bool = True,
    user_id: Optional[str] = None
) -> Session:
    """Create a new session."""
    return await db.session.create(
        data={
            "sessionId": session_id,
            "sessionStr": session_str,
            "label": label,
            "phone": phone,
            "enabled": enabled,
            "valid": valid,
            "version": 0,
            "userId": user_id
        }
    )


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
async def get_route(route_id: str) -> Optional[Route]:
    """Get a route by route_id."""
    return await db.route.find_unique(where={"routeId": route_id})


async def create_route(
    route_id: str,
    source_chat: str,
    target_chat: str,
    transform_type: str = "solana_ca",
    enabled: bool = True
) -> Route:
    """Create a new route."""
    return await db.route.create(
        data={
            "routeId": route_id,
            "sourceChat": source_chat,
            "targetChat": target_chat,
            "transformType": transform_type,
            "enabled": enabled
        }
    )


async def update_route(route_id: str, data: dict) -> Optional[Route]:
    """Update a route by route_id."""
    return await db.route.update(
        where={"routeId": route_id},
        data=data
    )


async def delete_route(route_id: str) -> Optional[Route]:
    """Delete a route by route_id."""
    return await db.route.delete(where={"routeId": route_id})


async def list_routes(enabled_only: bool = False) -> List[Route]:
    """List all routes, optionally filtered by enabled status."""
    if enabled_only:
        return await db.route.find_many(where={"enabled": True})
    return await db.route.find_many()


# Default session operations
async def get_default_session() -> Optional[DefaultSession]:
    """Get the default session setting."""
    sessions = await db.defaultsession.find_many()
    return sessions[0] if sessions else None


async def set_default_session(session_id: str) -> DefaultSession:
    """Set or update the default session."""
    existing = await get_default_session()
    if existing:
        return await db.defaultsession.update(
            where={"id": existing.id},
            data={"sessionId": session_id}
        )
    else:
        return await db.defaultsession.create(
            data={"sessionId": session_id}
        )
