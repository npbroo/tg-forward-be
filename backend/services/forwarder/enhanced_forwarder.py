"""
Enhanced Telegram forwarder with better error handling, session management, and recovery mechanisms.
"""
import asyncio
import re
from typing import Optional, Union, List, Dict, Tuple, Callable

from telethon import TelegramClient, events
from telethon.errors import (
    AuthKeyUnregisteredError,
    SessionPasswordNeededError,
    UserDeactivatedError,
    FloodWaitError,
    SlowModeWaitError,
    PhoneNumberBannedError,
    PhoneMigrateError,
    NetworkMigrateError,
)

from backend.services.session_manager import (
    EnhancedSessionManager,
    SessionRegistry,
    SessionErrorType,
)
from backend.services.target_resolver import TargetResolver
from backend.database import list_routes
from backend.services.events import event_emitter, EventType

try:
    from solders.pubkey import Pubkey
    SOLANA_AVAILABLE = True
except ImportError:
    SOLANA_AVAILABLE = False
    print("Warning: solders not installed. Solana address validation will be disabled.")


CA_REGEX = re.compile(r"(?<![1-9A-HJ-NP-Za-km-z])([1-9A-HJ-NP-Za-km-z]{32,44})(?![1-9A-HJ-NP-Za-km-z])")


def parse_chat_id(value: Union[str, int]) -> Union[str, int]:
    """Parse chat ID from string or int."""
    if isinstance(value, int):
        return value
    v = str(value).strip()
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    return v


def is_valid_solana_address(ca: str) -> bool:
    """Validate if a string is a valid Solana address."""
    if not SOLANA_AVAILABLE:
        # If solders is not available, do basic validation
        return len(ca) >= 32 and len(ca) <= 44

    try:
        Pubkey.from_string(ca)
        return True
    except Exception:
        return False


def transform_message_solana_ca(text: str) -> Optional[str]:
    """Extract and validate Solana contract address from text."""
    text = (text or "").strip()
    if not text:
        return None

    candidates = CA_REGEX.findall(text)
    for ca in candidates:
        if is_valid_solana_address(ca):
            return ca

    return None


def transform_message(text: str, transform_type: str) -> Optional[str]:
    """Transform message based on transform_type."""
    text = (text or "").strip()
    if not text:
        return None

    if transform_type == "raw":
        return text

    if transform_type == "solana_ca":
        return transform_message_solana_ca(text)

    # default fallback
    return text


class EnhancedForwarder:
    """
    Enhanced forwarder implementation with improved error handling, 
    session management, and recovery mechanisms.
    """
    
    def __init__(self):
        self.shutdown_event: Optional[asyncio.Event] = None
        self.active_client: Optional[TelegramClient] = None
        self.target_resolver: Optional[TargetResolver] = None
        self.is_running = False
        
        # Track consecutive failures for backoff
        self.consecutive_failures = 0
        self.max_backoff_time = 300  # 5 minutes max backoff
        
        # Track route errors separately from session errors
        self.route_error_counts: Dict[str, int] = {}
        self._route_event_handlers: List[Tuple[EventType, Callable]] = []
        self._client_event_handler: Optional[Tuple[Callable, object]] = None

    async def load_enabled_routes(self) -> List[Dict]:
        """Load all enabled routes from database."""
        routes = await list_routes(enabled_only=True)
        return [
            {
                "route_id": r.routeId,
                "source_chat": r.sourceChat,
                "target_chat": r.targetChat,
                "transform_type": r.transformType,
                "enabled": r.enabled
            }
            for r in routes
        ]

    def _remove_route_event_handlers(self):
        """Unsubscribe from route change events."""
        for event_type, handler in self._route_event_handlers:
            event_emitter.off(event_type, handler)
        self._route_event_handlers.clear()

    def _register_client_handler(
        self,
        client: TelegramClient,
        route_configs: List[Dict],
        session_id: str,
        source_filters: List[Union[int, str]],
    ):
        """Register the message handler for the current client."""
        if not source_filters:
            return

        self._remove_client_event_handler(client)
        message_event = events.NewMessage(chats=source_filters)

        async def handler(event: events.NewMessage.Event):
            await self.handle_message(event, route_configs, session_id)

        client.add_event_handler(handler, message_event)
        self._client_event_handler = (handler, message_event)

    def _remove_client_event_handler(self, client: Optional[TelegramClient]):
        """Detach the current message handler from the client."""
        if not client or not self._client_event_handler:
            return

        handler, event_builder = self._client_event_handler
        try:
            client.remove_event_handler(handler, event_builder)
        except Exception as exc:
            print(f"[CLEANUP] Failed to remove event handler: {exc}")
        finally:
            self._client_event_handler = None

    async def _shutdown_active_client(self):
        """Remove handlers and disconnect the active client."""
        client = self.active_client
        if not client:
            self.target_resolver = None
            return

        self._remove_client_event_handler(client)
        try:
            await client.disconnect()
        except Exception as exc:
            print(f"[CLEANUP] Error disconnecting client: {exc}")

        self.active_client = None
        self.target_resolver = None

    async def run_forwarder(self):
        """Main forwarder worker loop with event-based reload support."""
        # Event flag for route reload requests
        reload_event = asyncio.Event()

        # Register event listener for route changes
        async def on_route_change(_data):
            print(f"[EVENT] Route change detected, triggering reload...")
            reload_event.set()

        self._route_event_handlers = [
            (EventType.ROUTE_CREATED, on_route_change),
            (EventType.ROUTE_UPDATED, on_route_change),
            (EventType.ROUTE_DELETED, on_route_change),
        ]
        for event_type, handler in self._route_event_handlers:
            event_emitter.on(event_type, handler)

        print(f"[EVENT] Subscribed to route change events")

        try:
            # Check if there are any sessions available initially
            if not await SessionRegistry.is_session_available():
                print("[FORWARDER] No healthy sessions available, cannot start forwarder")
                return

            while True:
                # Calculate dynamic backoff based on failure count
                if self.consecutive_failures > 0:
                    backoff_time = min(5 * (2 ** min(self.consecutive_failures - 1, 6)), self.max_backoff_time)
                    print(f"[FORWARDER] Waiting {backoff_time}s before restart due to {self.consecutive_failures} consecutive failures...")
                    try:
                        await asyncio.sleep(backoff_time)
                    except asyncio.CancelledError:
                        print("[FORWARDER] Forwarder cancelled during backoff, shutting down...")
                        break

                # Create shutdown event for this instance
                self.shutdown_event = asyncio.Event()
                reload_event.clear()

                # Start forwarder instance
                forwarder_task = asyncio.create_task(self.run_forwarder_instance())

                # Listen for reload signals
                async def listen_for_signals():
                    await reload_event.wait()
                    print(f"[RELOAD] Received reload signal, restarting forwarder...")
                    self.shutdown_event.set()

                signal_listener = asyncio.create_task(listen_for_signals())

                # Wait for either task to complete
                done, pending = await asyncio.wait(
                    [forwarder_task, signal_listener],
                    return_when=asyncio.FIRST_COMPLETED
                )

                # Cancel pending tasks
                for task in pending:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

                # Wait for forwarder to fully stop
                try:
                    await forwarder_task
                except asyncio.CancelledError:
                    print("[FORWARDER] Forwarder instance was cancelled")
                except Exception as e:
                    print(f"[ERROR] Forwarder instance failed with error: {e}")

                # Check if forwarder crashed or was intentionally reloaded
                if forwarder_task.done() and not self.shutdown_event.is_set():
                    # Forwarder exited on its own (due to error or no routes)
                    self.consecutive_failures += 1
                    print(f"[FORWARDER] Exited due to error (#{self.consecutive_failures}), will retry...")
                else:
                    # Reload signal received - reset failure counter
                    self.consecutive_failures = 0
                    print("[RELOAD] Restarting forwarder with new configuration...")
                    await asyncio.sleep(1)  # Brief pause before restart
        finally:
            self._remove_route_event_handlers()

    async def run_forwarder_instance(self):
        """
        Run a single instance of the forwarder.
        Returns when shutdown_event is set or client disconnects.
        """
        self.is_running = True
        if not self.shutdown_event:
            self.shutdown_event = asyncio.Event()

        try:
            session_id, session_str, session_data = await self.load_preferred_session()
        except RuntimeError as e:
            print(f"[FORWARDER] {e}")
            return

        # Initialize client and resolver
        manager = EnhancedSessionManager(session_str=session_str)
        client = manager.create_client()
        self.active_client = client

        try:
            # Load routes
            routes = await self.load_enabled_routes()
            if not routes:
                print("No enabled routes found.")
                return

            # Build normalized route configs
            route_configs: List[Dict] = []
            source_filters: List[Union[int, str]] = []

            for r in routes:
                src = parse_chat_id(r["source_chat"])
                tgt = parse_chat_id(r["target_chat"])

                cfg = {
                    "route_id": r["route_id"],
                    "source_chat": src,
                    "target_chat": tgt,
                    "transform_type": r.get("transform_type", "solana_ca"),
                    "enabled": r.get("enabled", True),
                }
                route_configs.append(cfg)
                source_filters.append(src)

            # Set up message handler
            self._register_client_handler(client, route_configs, session_id, source_filters)

            # Connect to Telegram
            try:
                await client.connect()
                
                # Validate session health
                is_authorized = await client.is_user_authorized()
                if not is_authorized:
                    await SessionRegistry.mark_session_invalid(session_id, "Session not authorized")
                    print("[FORWARDER] Session not authorized; marking invalid and stopping.")
                    return
                
                # Update session health
                await SessionRegistry.mark_session_checked_ok(session_id)

            except Exception as e:
                error_type = self._classify_error(e)
                error_msg = f"{type(e).__name__}: {e}"
                
                if error_type == SessionErrorType.AUTH_ERROR:
                    await SessionRegistry.mark_session_invalid(session_id, error_msg, error_type)
                    print(f"[FORWARDER] Auth error; marking session invalid and stopping: {error_msg}")
                    return
                else:
                    print(f"[FORWARDER] Connection error (not auth-related): {error_msg}")
                    raise  # Re-raise for forwarder restart

            # Get user info for logging
            me = await client.get_me()
            print(f"Forwarder running as: {me.username or me.id}")

            # Initialize target resolver
            self.target_resolver = TargetResolver(client)
            
            # Resolve target entities using the new resolver
            for rc in route_configs:
                target_entity = await self.target_resolver.resolve_target(rc["target_chat"])
                if target_entity is None:
                    print(
                        f"[WARN] Could not resolve target_chat={rc['target_chat']!r} for route {rc['route_id']}. "
                        f"This route will be skipped."
                    )
                else:
                    rc["target_entity"] = target_entity

            print(f"[FORWARDER] Ready to forward from {len(source_filters)} sources to {len(route_configs)} routes")

            # Wait for shutdown signal
            try:
                await self.shutdown_event.wait()
                print("[RELOAD] Shutdown signal received, disconnecting...")
            finally:
                pass

        except asyncio.CancelledError:
            print("[FORWARDER] Forwarder instance cancelled")
        except Exception as e:
            print(f"[FORWARDER] Forwarder instance failed with error: {e}")
            raise
        finally:
            await self._shutdown_active_client()
            self.is_running = False
            print("[FORWARDER] Instance cleanup completed")

    async def handle_message(self, event: events.NewMessage.Event, route_configs: List[Dict], session_id: str):
        """Handle an incoming message and forward it according to configured routes."""
        ent = event.chat
        src_id = getattr(ent, "id", None)
        username = getattr(ent, "username", None)
        chat_id = event.chat_id

        # Find matching routes for this event
        matched_routes = []
        for rc in route_configs:
            src = rc["source_chat"]

            # Numeric match: compare absolute values to handle positive/negative IDs
            if isinstance(src, int):
                # Try matching with src_id first
                if isinstance(src_id, int) and src == src_id:
                    matched_routes.append(rc)
                # Also try matching with chat_id (handles negative IDs)
                elif abs(src) == abs(chat_id):
                    matched_routes.append(rc)

            # String match: treat as username
            elif isinstance(src, str) and username and src.lower() == username.lower():
                matched_routes.append(rc)

        if not matched_routes:
            return

        # Try raw_text first, fallback to text, then message attribute
        original_text = event.raw_text or event.text or getattr(event.message, 'message', '') or ""
        text_preview = original_text.replace('\n', ' ')[:60]

        for rc in matched_routes:
            new_text = transform_message(original_text, rc["transform_type"])

            if new_text is None:
                print(f"[SKIP] {rc['route_id']} | No match | {text_preview}...")
                continue

            print(f"[FORWARD] {rc['route_id']} | Matched: {new_text[:44]} | From: {text_preview}...")

            target_entity = rc.get("target_entity")
            if target_entity is None:
                # Try to resolve the target on-the-fly if not cached
                target_entity = await self.target_resolver.resolve_target(rc["target_chat"], force_refresh=True)
                if target_entity is None:
                    print(f"[SKIP] {rc['route_id']} | Target not resolved | {text_preview}...")
                    continue
                rc["target_entity"] = target_entity

            try:
                await self.active_client.send_message(target_entity, new_text)
                print(f"[SUCCESS] Message sent for route {rc['route_id']}")
            except Exception as e:
                await self.handle_send_error(e, rc['route_id'], session_id, text_preview)

    async def handle_send_error(self, error: Exception, route_id: str, session_id: str, text_preview: str):
        """Handle errors that occur during message sending."""
        error_type = self._classify_error(error)
        error_msg = f"{type(error).__name__}: {error}"

        # If this is a session-related error, mark the session as invalid
        if error_type == SessionErrorType.AUTH_ERROR:
            await SessionRegistry.mark_session_invalid(session_id, error_msg, error_type)
            print(f"[SESSION ERROR] Marking session {session_id} as invalid: {error_msg}")
            # Set shutdown event to allow failover to another session
            if self.shutdown_event:
                self.shutdown_event.set()
        elif error_type == SessionErrorType.RATE_LIMIT_ERROR:
            # Track route-specific rate limit errors
            self.route_error_counts[route_id] = self.route_error_counts.get(route_id, 0) + 1
            print(f"[RATE LIMIT] Route {route_id} hit rate limit: {error_msg}")
            # Don't mark session invalid, just log the issue
        elif error_type == SessionErrorType.NETWORK_ERROR:
            # Network errors are usually transient
            print(f"[NETWORK ERROR] Network issue for route {route_id}: {error_msg}")
        else:
            # Other errors might be route-specific
            self.route_error_counts[route_id] = self.route_error_counts.get(route_id, 0) + 1
            print(f"[ROUTE ERROR] Failed to send message for route {route_id}: {error_msg}")

    @staticmethod
    def _classify_error(error: Exception) -> SessionErrorType:
        """Classify an error to determine if it's session-related."""
        error_type = type(error)
        
        # Authentication-related errors - mark session as invalid
        auth_errors = (
            AuthKeyUnregisteredError, 
            UserDeactivatedError, 
            SessionPasswordNeededError,
            PhoneNumberBannedError,
        )
        
        if isinstance(error, auth_errors):
            return SessionErrorType.AUTH_ERROR
            
        # Rate limiting errors - don't mark session invalid
        rate_limit_errors = (
            FloodWaitError,
            SlowModeWaitError,
        )
        
        if isinstance(error, rate_limit_errors):
            return SessionErrorType.RATE_LIMIT_ERROR
            
        # Network-related errors - usually transient
        network_errors = (
            PhoneMigrateError,
            NetworkMigrateError,
        )
        
        if isinstance(error, network_errors):
            return SessionErrorType.NETWORK_ERROR
            
        # Default to transient error that doesn't affect session
        return SessionErrorType.TRANSIENT_ERROR

    async def load_preferred_session(self) -> Tuple[str, str, dict]:
        """Load the best available session."""
        session_id, session_str, session_data = await SessionRegistry.get_healthy_session()
        
        if not session_id:
            raise RuntimeError("No healthy sessions available")
            
        return session_id, session_str, session_data
