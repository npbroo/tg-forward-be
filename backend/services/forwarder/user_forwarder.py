"""
User-specific forwarder worker.
Each user gets their own forwarder instance that uses their Telegram session.
"""
import asyncio
from typing import Optional

from backend.database import db
from backend.services.forwarder.enhanced_forwarder import EnhancedForwarder
from backend.services.events import event_emitter, EventType


class UserForwarderWorker:
    """
    Forwarder worker dedicated to a single user account.
    Manages the user's Telegram session and forwards messages according to routes.
    """

    def __init__(self, user_id: str, username: str):
        self.user_id = user_id
        self.username = username
        self.forwarder: Optional[EnhancedForwarder] = None
        self.forwarder_task: Optional[asyncio.Task] = None
        self._session_created_handler = None
        self._session_invalidated_handler = None
        self.is_running = False

    async def start(self):
        """Start the forwarder worker for this user."""
        if self.is_running:
            print(f"[USER-WORKER:{self.username}] Already running")
            return

        print(f"[USER-WORKER:{self.username}] Starting worker for user {self.user_id}")
        self.is_running = True
        self._session_created_handler = self._on_session_created
        self._session_invalidated_handler = self._on_session_invalidated

        event_emitter.on_user(
            EventType.SESSION_CREATED,
            self.user_id,
            self._session_created_handler,
        )
        event_emitter.on_user(
            EventType.SESSION_INVALIDATED,
            self.user_id,
            self._session_invalidated_handler,
        )

        await self._start_forwarder_if_session_available()

    async def stop(self):
        """Stop the forwarder worker for this user."""
        if not self.is_running:
            return

        print(f"[USER-WORKER:{self.username}] Stopping worker")
        self.is_running = False

        if self._session_created_handler:
            event_emitter.off_user(
                EventType.SESSION_CREATED,
                self.user_id,
                self._session_created_handler,
            )
            self._session_created_handler = None

        if self._session_invalidated_handler:
            event_emitter.off_user(
                EventType.SESSION_INVALIDATED,
                self.user_id,
                self._session_invalidated_handler,
            )
            self._session_invalidated_handler = None

        await self._stop_forwarder()
        print(f"[USER-WORKER:{self.username}] Worker stopped")

    async def _on_session_created(self, _data):
        """Handle session creation events by ensuring the forwarder is running."""
        if not self.is_running:
            return

        print(f"[USER-WORKER:{self.username}] Session created event received")
        await self._start_forwarder_if_session_available(force_restart=True)

    async def _on_session_invalidated(self, _data):
        """Handle session invalidation events by stopping the forwarder."""
        if not self.is_running:
            return

        print(f"[USER-WORKER:{self.username}] Session invalidated event received")
        await self._stop_forwarder()

    async def _start_forwarder_if_session_available(self, *, force_restart: bool = False):
        """Start the forwarder if a valid session exists."""
        if not self.is_running:
            return

        session = await self._get_user_session()
        if not session:
            return

        if self.forwarder_task and not self.forwarder_task.done():
            if not force_restart:
                return
            await self._stop_forwarder()

        await self._launch_forwarder(session)

    async def _launch_forwarder(self, session):
        """Launch a forwarder instance bound to the provided session."""
        if not self.is_running:
            return

        print(f"[USER-WORKER:{self.username}] Launching session {session.sessionId}")
        self.forwarder = EnhancedForwarder(user_id=self.user_id)

        async def load_user_session():
            fresh_session = await self._get_user_session()
            if not fresh_session:
                raise RuntimeError(f"No valid session for user {self.username}")

            return fresh_session.sessionId, fresh_session.sessionStr, {
                "session_id": fresh_session.sessionId,
                "session_str": fresh_session.sessionStr,
                "label": fresh_session.label,
                "phone": fresh_session.phone,
                "enabled": fresh_session.enabled,
                "valid": fresh_session.valid,
                "version": fresh_session.version
            }

        self.forwarder.load_preferred_session = load_user_session
        self.forwarder_task = asyncio.create_task(self._run_forwarder())
        self.forwarder_task.add_done_callback(self._forwarder_task_done)

    async def _run_forwarder(self):
        """Run the forwarder until it stops or is shut down."""
        assert self.forwarder is not None
        await self.forwarder.run_forwarder()

    def _forwarder_task_done(self, task: asyncio.Task):
        """Cleanup helper when the forwarder task stops."""
        exception = None
        try:
            exception = task.exception()
        except asyncio.CancelledError:
            pass

        if exception:
            print(f"[USER-WORKER:{self.username}] Forwarder task finished with error: {exception}")

        self.forwarder = None
        self.forwarder_task = None

    async def _stop_forwarder(self):
        """Stop the running forwarder task if present."""
        if not self.forwarder:
            return

        if self.forwarder.shutdown_event:
            self.forwarder.shutdown_event.set()

        if self.forwarder_task:
            try:
                await asyncio.wait_for(self.forwarder_task, timeout=10.0)
            except asyncio.TimeoutError:
                print(f"[USER-WORKER:{self.username}] Forwarder did not stop, cancelling task")
                self.forwarder_task.cancel()
                try:
                    await self.forwarder_task
                except asyncio.CancelledError:
                    pass

        self.forwarder = None
        self.forwarder_task = None

    async def _get_user_session(self):
        """Get the user's active Telegram session from the database."""

        # Find sessions for this user that are valid and enabled
        sessions = await db.session.find_many(
            where={
                "userId": self.user_id,
                "enabled": True,
                "valid": True
            },
            order={"lastActivity": "desc"}
        )

        if not sessions:
            return None

        # Return the most recently active session
        return sessions[0]
