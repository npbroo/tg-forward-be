"""
Enhanced session management with versioning, locking, and health checks.
"""
import asyncio
import time
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Tuple, List
from enum import Enum

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import (
    AuthKeyUnregisteredError,
    SessionPasswordNeededError,
    UserDeactivatedError,
    FloodWaitError,
    PhoneMigrateError,
    NetworkMigrateError,
)

from config import settings
from shared.redis_client import redis_get_json, redis_set_json, redis_scan_json, redis_client
from shared.pubsub import notify_forwarder_reload


class SessionStatus(Enum):
    HEALTHY = "healthy"
    INVALID = "invalid"
    DISABLED = "disabled"
    PENDING = "pending"


class SessionErrorType(Enum):
    AUTH_ERROR = "auth_error"
    NETWORK_ERROR = "network_error"
    RATE_LIMIT_ERROR = "rate_limit_error"
    TRANSIENT_ERROR = "transient_error"


class EnhancedSessionManager:
    """
    Enhanced session manager with versioning, locking, and health validation.
    """
    
    def __init__(self, session_str: str | None = None):
        self.api_id = settings.TG_API_ID
        self.api_hash = settings.TG_API_HASH
        self.session_str = session_str

    def create_client(self) -> TelegramClient:
        """Create a new Telegram client with the session."""
        if self.session_str:
            session = StringSession(self.session_str)
        else:
            session = StringSession()
        return TelegramClient(session, self.api_id, self.api_hash)

    async def is_session_healthy(self, session_str: str) -> Tuple[bool, Optional[str]]:
        """
        Check if the session is healthy without keeping the connection open.
        
        Returns:
            Tuple[bool, Optional[str]]: (is_healthy, error_message)
        """
        try:
            manager = EnhancedSessionManager(session_str=session_str)
            client = manager.create_client()
            await client.connect()
            
            if not await client.is_user_authorized():
                await client.disconnect()
                return False, "Session not authorized"
                
            await client.disconnect()
            return True, None
        except (AuthKeyUnregisteredError, UserDeactivatedError, SessionPasswordNeededError) as e:
            return False, f"{type(e).__name__}: {e}"
        except Exception as e:
            return False, f"Connection error: {e}"


class SessionRegistry:
    """
    Registry to manage session states, versions, and locking.
    """
    
    @staticmethod
    async def get_session_version(session_id: str) -> Optional[int]:
        """Get the current version of a session."""
        session = await redis_get_json(f"tg:session:{session_id}")
        return session.get("version", 0) if session else None

    @staticmethod
    async def increment_session_version(session_id: str) -> int:
        """Increment session version to invalidate cached references."""
        session = await redis_get_json(f"tg:session:{session_id}")
        if not session:
            return 0
            
        new_version = session.get("version", 0) + 1
        session["version"] = new_version
        await redis_set_json(f"tg:session:{session_id}", session)
        return new_version

    @staticmethod
    async def acquire_session_lock(session_id: str, lock_duration: int = 30) -> Optional[str]:
        """
        Acquire a lock for a session to prevent concurrent access.
        
        Args:
            session_id: ID of the session to lock
            lock_duration: Duration in seconds for the lock
            
        Returns:
            lock_id if successful, None if already locked
        """
        lock_key = f"tg:session:lock:{session_id}"
        lock_id = str(uuid.uuid4())
        
        from shared.redis_client import redis_client
        # Use Redis SET with NX (only set if not exists) and EX (expire)
        result = await redis_client.set(
            lock_key,
            lock_id,
            nx=True,  # Only set if key doesn't exist
            ex=lock_duration  # Expire after duration seconds
        )
        
        return lock_id if result else None

    @staticmethod
    async def release_session_lock(session_id: str, lock_id: str) -> bool:
        """
        Release a session lock using the lock ID.
        
        Args:
            session_id: ID of the session to unlock
            lock_id: The lock ID returned when acquiring the lock
            
        Returns:
            True if successfully released, False otherwise
        """
        from shared.redis_client import redis_client
        lock_key = f"tg:session:lock:{session_id}"
        
        # Lua script to atomically check and delete the lock
        lua_script = """
        if redis.call("GET", KEYS[1]) == ARGV[1] then
            return redis.call("DEL", KEYS[1])
        else
            return 0
        end
        """
        
        result = await redis_client.eval(
            lua_script, 
            keys=[lock_key], 
            args=[lock_id]
        )
        
        return result == 1

    @staticmethod
    async def mark_session_invalid(session_id: str, reason: str, error_type: SessionErrorType = SessionErrorType.AUTH_ERROR):
        """Mark the given session as invalid/disabled with error metadata."""
        key = f"tg:session:{session_id}"
        session = await redis_get_json(key)
        if not session:
            return

        session["enabled"] = False
        session["valid"] = False
        session["last_error"] = reason
        session["error_type"] = error_type.value
        session["last_checked"] = datetime.now(timezone.utc).isoformat()

        # Increment version to indicate this session is now invalid
        session["version"] = session.get("version", 0) + 1

        await redis_set_json(key, session)
        await notify_forwarder_reload("session_invalidated")

    @staticmethod
    async def mark_session_checked_ok(session_id: str):
        """Refresh metadata when a session is healthy."""
        key = f"tg:session:{session_id}"
        session = await redis_get_json(key)
        if not session:
            return

        session["valid"] = True
        session.setdefault("enabled", True)
        session["last_error"] = None
        session["error_type"] = None
        session["last_checked"] = datetime.now(timezone.utc).isoformat()
        session["last_activity"] = datetime.now(timezone.utc).isoformat()

        await redis_set_json(key, session)

    @staticmethod
    async def get_healthy_session() -> Tuple[Optional[str], Optional[str], Optional[dict]]:
        """
        Get the best available healthy session.
        Prioritizes default session, then falls back to other valid sessions.
        """
        # First try the default session
        default = await redis_get_json("tg:session:default")
        if default and "session_id" in default:
            session_id = default["session_id"]
            session = await redis_get_json(f"tg:session:{session_id}")
            
            if (session and 
                session.get("enabled", True) and 
                session.get("valid", True)):
                
                # Verify session is actually usable
                manager = EnhancedSessionManager(session_str=session["session_str"])
                is_healthy, _ = await manager.is_session_healthy(session["session_str"])
                
                if is_healthy:
                    return session_id, session["session_str"], session

        # Fallback to other valid sessions 
        sessions = await redis_scan_json("tg:session:sess_*")
        for candidate_session in sessions:
            if (candidate_session.get("enabled", True) and 
                candidate_session.get("valid", True)):
                
                manager = EnhancedSessionManager(session_str=candidate_session["session_str"])
                is_healthy, _ = await manager.is_session_healthy(candidate_session["session_str"])
                
                if is_healthy:
                    return (candidate_session["session_id"], 
                           candidate_session["session_str"], 
                           candidate_session)

        return None, None, None

    @staticmethod
    async def is_session_available() -> bool:
        """
        Check if there's at least one healthy session available.
        """
        session_id, _, _ = await SessionRegistry.get_healthy_session()
        return session_id is not None


# For backward compatibility
async def mark_session_invalid(session_id: str, reason: str):
    """Legacy function for backward compatibility."""
    await SessionRegistry.mark_session_invalid(session_id, reason)


async def mark_session_checked_ok(session_id: str):
    """Legacy function for backward compatibility."""
    await SessionRegistry.mark_session_checked_ok(session_id)