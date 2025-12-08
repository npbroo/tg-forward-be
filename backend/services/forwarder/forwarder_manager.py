"""
Forwarder Manager - Spawns and manages one forwarder worker per user.
"""
import asyncio
from typing import Dict
from backend.services.forwarder.user_forwarder import UserForwarderWorker
from backend.database import list_users
from backend.services.events import event_emitter, EventType


class ForwarderManager:
    """
    Manages multiple forwarder workers, one per user account.
    """

    def __init__(self):
        self.workers: Dict[str, UserForwarderWorker] = {}  # user_id -> worker
        self.is_running = False
        self._user_created_handler = None
        self._user_deleted_handler = None

    async def start(self):
        """Start the forwarder manager and spawn workers for all users."""
        if self.is_running:
            print("[FORWARDER-MANAGER] Already running")
            return

        print("[FORWARDER-MANAGER] Starting forwarder manager")
        self.is_running = True

        # Register event listeners for user creation/deletion
        self._user_created_handler = self._handle_user_created
        self._user_deleted_handler = self._handle_user_deleted
        event_emitter.on(EventType.USER_CREATED, self._user_created_handler)
        event_emitter.on(EventType.USER_DELETED, self._user_deleted_handler)

        # Spawn workers for all existing users
        await self._spawn_all_workers()

        print(f"[FORWARDER-MANAGER] Started with {len(self.workers)} workers")

    async def stop(self):
        """Stop all forwarder workers."""
        if not self.is_running:
            return

        print("[FORWARDER-MANAGER] Stopping forwarder manager")
        self.is_running = False

        if self._user_created_handler:
            event_emitter.off(EventType.USER_CREATED, self._user_created_handler)
            self._user_created_handler = None

        if self._user_deleted_handler:
            event_emitter.off(EventType.USER_DELETED, self._user_deleted_handler)
            self._user_deleted_handler = None

        # Stop all workers
        await self._stop_all_workers()

        print("[FORWARDER-MANAGER] Stopped")

    async def _spawn_all_workers(self):
        """Spawn a worker for each user in the database."""
        users = await list_users()

        for user in users:
            await self._spawn_worker(user.id, user.username)

    async def _spawn_worker(self, user_id: str, username: str):
        """Spawn a forwarder worker for a specific user."""
        if user_id in self.workers:
            print(f"[FORWARDER-MANAGER] Worker for user {username} already exists")
            return

        print(f"[FORWARDER-MANAGER] Spawning worker for user {username} ({user_id})")
        worker = UserForwarderWorker(user_id, username)
        self.workers[user_id] = worker
        await worker.start()

    async def _stop_all_workers(self):
        """Stop all running workers."""
        print(f"[FORWARDER-MANAGER] Stopping {len(self.workers)} workers")

        stop_tasks = [worker.stop() for worker in self.workers.values()]
        if stop_tasks:
            await asyncio.gather(*stop_tasks, return_exceptions=True)

        self.workers.clear()

    async def _stop_worker(self, user_id: str):
        """Stop a specific worker."""
        worker = self.workers.get(user_id)
        if worker:
            await worker.stop()
            del self.workers[user_id]
            print(f"[FORWARDER-MANAGER] Stopped worker for user {user_id}")

    async def _handle_user_created(self, data):
        """Handle user creation events by spawning a worker."""
        user_id = data.get("user_id")
        username = data.get("username")
        if user_id and username:
            print(f"[FORWARDER-MANAGER] User created: {username}")
            await self._spawn_worker(user_id, username)

    async def _handle_user_deleted(self, data):
        """Handle user deletion events by stopping the worker."""
        user_id = data.get("user_id")
        if user_id:
            print(f"[FORWARDER-MANAGER] User deleted: {user_id}")
            await self._stop_worker(user_id)


# Global manager instance
_manager: ForwarderManager = None


async def get_forwarder_manager() -> ForwarderManager:
    """Get the global forwarder manager instance."""
    global _manager
    if _manager is None:
        _manager = ForwarderManager()
    return _manager


async def start_forwarder_manager():
    """Start the global forwarder manager."""
    manager = await get_forwarder_manager()
    await manager.start()


async def stop_forwarder_manager():
    """Stop the global forwarder manager."""
    global _manager
    if _manager:
        await _manager.stop()
        _manager = None
