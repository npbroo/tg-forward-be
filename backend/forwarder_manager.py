"""
Forwarder Manager - Spawns and manages one forwarder worker per user.
"""
import asyncio
from typing import Dict
from user_forwarder import UserForwarderWorker
from database import list_users
from shared.redis_client import redis_client


class ForwarderManager:
    """
    Manages multiple forwarder workers, one per user account.
    """

    def __init__(self):
        self.workers: Dict[str, UserForwarderWorker] = {}  # user_id -> worker
        self.is_running = False
        self.pubsub_task: asyncio.Task = None

    async def start(self):
        """Start the forwarder manager and spawn workers for all users."""
        if self.is_running:
            print("[FORWARDER-MANAGER] Already running")
            return

        print("[FORWARDER-MANAGER] Starting forwarder manager")
        self.is_running = True

        # Spawn workers for all existing users
        await self._spawn_all_workers()

        # Start listening for reload signals
        self.pubsub_task = asyncio.create_task(self._listen_for_signals())

        print(f"[FORWARDER-MANAGER] Started with {len(self.workers)} workers")

    async def stop(self):
        """Stop all forwarder workers."""
        if not self.is_running:
            return

        print("[FORWARDER-MANAGER] Stopping forwarder manager")
        self.is_running = False

        # Stop pubsub listener
        if self.pubsub_task:
            self.pubsub_task.cancel()
            try:
                await self.pubsub_task
            except asyncio.CancelledError:
                pass

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

    async def _reload_worker(self, user_id: str):
        """Reload a specific worker."""
        worker = self.workers.get(user_id)
        if worker:
            await worker.reload()
            print(f"[FORWARDER-MANAGER] Reloaded worker for user {user_id}")

    async def _reload_all_workers(self):
        """Reload all workers (e.g., when routes change)."""
        print(f"[FORWARDER-MANAGER] Reloading all {len(self.workers)} workers")

        reload_tasks = [worker.reload() for worker in self.workers.values()]
        if reload_tasks:
            await asyncio.gather(*reload_tasks, return_exceptions=True)

    async def _listen_for_signals(self):
        """Listen for reload/control signals from Redis pub/sub."""
        pubsub = redis_client.pubsub()
        await pubsub.subscribe("forwarder:reload", "forwarder:control", "forwarder:user")

        print("[FORWARDER-MANAGER] Listening for signals")

        try:
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue

                channel = message["channel"]
                data = message["data"].decode() if isinstance(message["data"], bytes) else message["data"]

                print(f"[FORWARDER-MANAGER] Received signal on {channel}: {data}")

                if channel == "forwarder:control":
                    if data == "shutdown":
                        print("[FORWARDER-MANAGER] Shutdown signal received")
                        break
                    elif data == "reload_all":
                        await self._reload_all_workers()

                elif channel == "forwarder:reload":
                    # General reload signal (routes changed, etc.)
                    await self._reload_all_workers()

                elif channel == "forwarder:user":
                    # User-specific signals: "user_created:<user_id>", "user_deleted:<user_id>", "session_created:<user_id>"
                    if data.startswith("user_created:"):
                        user_id = data.split(":", 1)[1]
                        # Fetch user from database and spawn worker
                        from database import get_user_by_id
                        user = await get_user_by_id(user_id)
                        if user:
                            await self._spawn_worker(user.id, user.username)

                    elif data.startswith("user_deleted:"):
                        user_id = data.split(":", 1)[1]
                        await self._stop_worker(user_id)

                    elif data.startswith("session_created:") or data.startswith("session_updated:"):
                        # Reload the specific user's worker when their session changes
                        user_id = data.split(":", 1)[1]
                        await self._reload_worker(user_id)

        except asyncio.CancelledError:
            print("[FORWARDER-MANAGER] Signal listener cancelled")
        finally:
            await pubsub.unsubscribe()
            await pubsub.close()


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
