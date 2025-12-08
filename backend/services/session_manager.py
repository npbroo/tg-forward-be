"""
Enhanced session management with versioning, locking, and health checks.
"""
from datetime import datetime, timezone
from typing import Optional, Tuple
from enum import Enum

from telethon import TelegramClient
from telethon.sessions import StringSession

from backend.core.config import settings
from backend.database import (
    get_session, update_session, get_valid_sessions
)
from backend.services.events import emit_session_invalidated


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


class SessionRegistry:
    """
    Registry to manage session states, versions, and locking.
    """

    @staticmethod
    async def get_session_version(session_id: str) -> Optional[int]:
        """Get the current version of a session."""
        session = await get_session(session_id)
        return session.version if session else None

    @staticmethod
    async def increment_session_version(session_id: str) -> int:
        """Increment session version to invalidate cached references."""
        session = await get_session(session_id)
        if not session:
            return 0

        new_version = session.version + 1
        await update_session(session_id, {"version": new_version})
        return new_version

    # Note: Session locking removed - using database row-level locking if needed
    # For concurrent access control, use MySQL SELECT ... FOR UPDATE

    @staticmethod
    async def mark_session_invalid(session_id: str, reason: str, error_type: SessionErrorType = SessionErrorType.AUTH_ERROR):
        """Mark the given session as invalid/disabled with error metadata."""
        session = await get_session(session_id)
        if not session:
            return

        await update_session(session_id, {
            "enabled": False,
            "valid": False,
            "lastError": reason,
            "errorType": error_type.value,
            "lastChecked": datetime.now(timezone.utc),
            "version": session.version + 1
        })

        # Emit session invalidated event for the user's worker
        if session.userId:
            await emit_session_invalidated(session.userId)

    @staticmethod
    async def mark_session_checked_ok(session_id: str):
        """Refresh metadata when a session is healthy."""
        session = await get_session(session_id)
        if not session:
            return

        await update_session(session_id, {
            "valid": True,
            "enabled": True,
            "lastError": None,
            "errorType": None,
            "lastChecked": datetime.now(timezone.utc),
            "lastActivity": datetime.now(timezone.utc)
        })

    @staticmethod
    async def get_healthy_session() -> Tuple[Optional[str], Optional[str], Optional[dict]]:
        """
        Get the best available healthy session from all valid sessions.
        Relies on session metadata updated by forwarders when Telethon raises errors.
        """
        sessions = await get_valid_sessions()
        if not sessions:
            return None, None, None

        session = sessions[0]
        return (
            session.sessionId,
            session.sessionStr,
            {
                "session_id": session.sessionId,
                "session_str": session.sessionStr,
                "label": session.label,
                "phone": session.phone,
                "enabled": session.enabled,
                "valid": session.valid,
                "version": session.version,
            },
        )

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
