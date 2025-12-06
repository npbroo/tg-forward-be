"""Redis pub/sub utilities for notifying the forwarder of configuration changes."""

from shared.redis_client import redis_client

FORWARDER_RELOAD_CHANNEL = "forwarder:reload"


async def notify_forwarder_reload(reason: str = "config_change"):
    """
    Publish a reload signal to the forwarder.

    Args:
        reason: Description of why the reload is needed (e.g., "route_updated", "session_changed")
    """
    await redis_client.publish(FORWARDER_RELOAD_CHANNEL, reason)
    print(f"[PUBSUB] Published reload signal: {reason}")
