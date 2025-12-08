"""
User-specific forwarder worker.
Each user gets their own forwarder instance that uses their Telegram session.
"""
import asyncio
from typing import Optional
from enhanced_forwarder import EnhancedForwarder
from database import get_user_by_id, get_session
from session_manager import SessionRegistry
from events import event_emitter, EventType


class UserForwarderWorker:
    """
    Forwarder worker dedicated to a single user account.
    Manages the user's Telegram session and forwards messages according to routes.
    """

    def __init__(self, user_id: str, username: str):
        self.user_id = user_id
        self.username = username
        self.forwarder: Optional[EnhancedForwarder] = None
        self.worker_task: Optional[asyncio.Task] = None
        self.shutdown_event = asyncio.Event()
        self.session_created_event = asyncio.Event()
        self.session_invalidated_event = asyncio.Event()
        self.is_running = False

    async def start(self):
        """Start the forwarder worker for this user."""
        if self.is_running:
            print(f"[USER-WORKER:{self.username}] Already running")
            return

        print(f"[USER-WORKER:{self.username}] Starting worker for user {self.user_id}")
        self.is_running = True
        self.shutdown_event.clear()

        # Register event listeners for this user
        async def on_session_created(data):
            print(f"[USER-WORKER:{self.username}] Session created event received")
            self.session_created_event.set()

        async def on_session_invalidated(data):
            print(f"[USER-WORKER:{self.username}] Session invalidated event received")
            self.session_invalidated_event.set()
            # Stop the forwarder if running
            if self.forwarder and self.forwarder.shutdown_event:
                self.forwarder.shutdown_event.set()

        event_emitter.on_user(EventType.SESSION_CREATED, self.user_id, on_session_created)
        event_emitter.on_user(EventType.SESSION_INVALIDATED, self.user_id, on_session_invalidated)

        # Start the worker task
        self.worker_task = asyncio.create_task(self._run_worker())

    async def stop(self):
        """Stop the forwarder worker for this user."""
        if not self.is_running:
            return

        print(f"[USER-WORKER:{self.username}] Stopping worker")
        self.shutdown_event.set()

        if self.worker_task:
            try:
                await asyncio.wait_for(self.worker_task, timeout=10.0)
            except asyncio.TimeoutError:
                print(f"[USER-WORKER:{self.username}] Worker did not stop gracefully, cancelling")
                self.worker_task.cancel()
                try:
                    await self.worker_task
                except asyncio.CancelledError:
                    pass

        self.is_running = False
        print(f"[USER-WORKER:{self.username}] Worker stopped")

    async def _run_worker(self):
        """
        Main worker loop. Waits for session events and manages forwarder lifecycle.
        """
        try:
            while not self.shutdown_event.is_set():
                # Check if user has a valid session
                session = await self._get_user_session()

                if not session:
                    print(f"[USER-WORKER:{self.username}] No valid session found, waiting for session creation...")
                    # Wait for session creation event or shutdown
                    self.session_created_event.clear()
                    done, pending = await asyncio.wait(
                        [
                            asyncio.create_task(self.session_created_event.wait()),
                            asyncio.create_task(self.shutdown_event.wait())
                        ],
                        return_when=asyncio.FIRST_COMPLETED
                    )
                    # Cancel pending tasks
                    for task in pending:
                        task.cancel()
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass

                    if self.shutdown_event.is_set():
                        break  # Shutdown requested
                    continue  # Session created, loop to start forwarder

                # Create and run forwarder instance
                print(f"[USER-WORKER:{self.username}] Starting forwarder with session {session.sessionId}")
                self.forwarder = EnhancedForwarder()

                # Override the load_preferred_session to use this user's session
                async def load_user_session():
                    # Get fresh session data
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

                try:
                    # Run the forwarder (will run until shutdown or session invalidated)
                    await self.forwarder.run_forwarder()
                except Exception as e:
                    print(f"[USER-WORKER:{self.username}] Forwarder error: {e}")
                    # Wait a bit before retrying
                    try:
                        await asyncio.wait_for(self.shutdown_event.wait(), timeout=10.0)
                        break  # Shutdown requested
                    except asyncio.TimeoutError:
                        continue  # Retry

                # Check if session was invalidated
                if self.session_invalidated_event.is_set():
                    print(f"[USER-WORKER:{self.username}] Session invalidated, waiting for new session...")
                    self.session_invalidated_event.clear()
                    continue  # Loop back to wait for new session

        except asyncio.CancelledError:
            print(f"[USER-WORKER:{self.username}] Worker cancelled")
        except Exception as e:
            print(f"[USER-WORKER:{self.username}] Worker error: {e}")
        finally:
            if self.forwarder and self.forwarder.shutdown_event:
                self.forwarder.shutdown_event.set()
            self.is_running = False

    async def _get_user_session(self):
        """Get the user's active Telegram session from the database."""
        from database import db

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

    async def reload(self):
        """Reload the forwarder (e.g., when routes change)."""
        if self.forwarder and self.forwarder.shutdown_event:
            print(f"[USER-WORKER:{self.username}] Reloading forwarder")
            self.forwarder.shutdown_event.set()
