"""
Robust target resolution system with caching and fallback mechanisms.
"""
import time
from typing import Dict, List, Optional, Union
from dataclasses import dataclass

from telethon import TelegramClient
from telethon.tl.custom.dialog import Dialog
from telethon.errors import RPCError


@dataclass
class TargetResolution:
    """Represents the resolution of a target chat."""
    target_chat: Union[str, int]
    resolved_entity: Optional[object] = None
    last_resolved: float = 0.0
    error: Optional[str] = None
    attempts: int = 0


class TargetResolver:
    """
    Advanced target resolver with caching, fallback mechanisms, and refresh capabilities.
    """
    
    def __init__(self, client: TelegramClient, cache_ttl: int = 3600):  # 1 hour default TTL
        self.client = client
        self.cache_ttl = cache_ttl
        self.resolutions: Dict[Union[str, int], TargetResolution] = {}
        self.channels: List[Dialog] = []
        self.channels_last_fetched: float = 0.0
        self.channels_ttl: int = 1800  # 30 minutes default TTL for channels

    async def get_channels(self, force_refresh: bool = False) -> List[Dialog]:
        """
        Get channels with caching and TTL management.

        Args:
            force_refresh: If True, ignores cache and fetches fresh channels

        Returns:
            List of channels
        """
        current_time = time.time()

        # Check if we need to refresh channels
        if (force_refresh or
            not self.channels or
            current_time - self.channels_last_fetched > self.channels_ttl):

            try:
                self.channels = await self.client.get_dialogs(limit=None)
                self.channels_last_fetched = current_time
            except RPCError as e:
                # Log the error but return cached channels if available
                print(f"[WARN] Error fetching channels: {e}")
                if not self.channels:
                    # If no cached channels, re-raise the error
                    raise

        return self.channels

    async def resolve_target(self, target_chat: Union[str, int], force_refresh: bool = False) -> Optional[object]:
        """
        Resolve a target chat to a Telegram entity with caching and refresh capabilities.
        
        Args:
            target_chat: The chat ID (int) or username/title (str) to resolve
            force_refresh: If True, forces a fresh resolution attempt
            
        Returns:
            Telegram entity if found, None otherwise
        """
        cache_key = target_chat
        current_time = time.time()
        
        # Check if we have a cached resolution
        resolution = self.resolutions.get(cache_key)
        
        if (resolution and 
            not force_refresh and 
            current_time - resolution.last_resolved < self.cache_ttl and 
            resolution.resolved_entity):
            
            return resolution.resolved_entity

        # Perform resolution
        entity = await self._resolve_single_target(target_chat)
        
        # Update cache
        if cache_key in self.resolutions:
            self.resolutions[cache_key].resolved_entity = entity
            self.resolutions[cache_key].last_resolved = current_time
            self.resolutions[cache_key].error = None if entity else "Target not found"
            self.resolutions[cache_key].attempts += 1
        else:
            self.resolutions[cache_key] = TargetResolution(
                target_chat=target_chat,
                resolved_entity=entity,
                last_resolved=current_time,
                error=None if entity else "Target not found",
                attempts=1
            )
        
        return entity

    async def _resolve_single_target(self, target_chat: Union[str, int]) -> Optional[object]:
        """
        Internal method to resolve a single target chat to an entity.
        """
        channels = await self.get_channels()

        if isinstance(target_chat, int):
            # Match by numeric ID - handle both positive and negative IDs
            abs_target = abs(target_chat)
            for channel in channels:
                ent = channel.entity
                ent_id = getattr(ent, "id", None)
                if ent_id and abs(ent_id) == abs_target:
                    return ent
        else:
            # String match - try username, title, or name
            target_lower = str(target_chat).lower().strip()
            for dialog in dialogs:
                ent = dialog.entity
                
                # Get entity attributes
                username = getattr(ent, "username", None)
                title = getattr(ent, "title", None)
                first_name = getattr(ent, "first_name", None)
                last_name = getattr(ent, "last_name", None)
                
                # Construct name variations
                full_name = f"{first_name or ''} {last_name or ''}".strip()
                entity_name = (title or full_name or "").lower()
                
                # Match username or name
                if ((username and target_lower == username.lower()) or
                    (title and target_lower == title.lower()) or
                    (full_name and target_lower == full_name.lower()) or
                    (entity_name and target_lower == entity_name)):
                    return ent

        # If direct match fails, try partial matching as a fallback
        return await self._resolve_with_partial_match(target_chat)

    async def _resolve_with_partial_match(self, target_chat: Union[str, int]) -> Optional[object]:
        """
        Fallback method to resolve targets with partial matching.
        """
        if not isinstance(target_chat, str):
            return None
            
        channels = await self.get_channels()
        target_lower = target_chat.lower().strip()

        # Try partial matches (first 3+ chars match)
        for channel in channels:
            ent = channel.entity
            username = getattr(ent, "username", None)
            title = getattr(ent, "title", None)
            first_name = getattr(ent, "first_name", None)
            last_name = getattr(ent, "last_name", None)
            
            full_name = f"{first_name or ''} {last_name or ''}".strip()
            entity_name = (title or full_name or "").lower()
            
            if ((username and len(target_lower) >= 3 and username.lower().startswith(target_lower)) or
                (title and len(target_lower) >= 3 and title.lower().startswith(target_lower)) or
                (full_name and len(target_lower) >= 3 and full_name.lower().startswith(target_lower))):
                # Double-check this is the right entity
                return ent
                
        return None

    def invalidate_resolution(self, target_chat: Union[str, int]):
        """
        Remove a target from the cache to force re-resolution.
        """
        if target_chat in self.resolutions:
            del self.resolutions[target_chat]

    def invalidate_all_resolutions(self):
        """
        Clear all cached resolutions.
        """
        self.resolutions.clear()

    async def refresh_target(self, target_chat: Union[str, int]) -> Optional[object]:
        """
        Force refresh resolution for a specific target.
        """
        return await self.resolve_target(target_chat, force_refresh=True)

    async def refresh_all(self):
        """
        Refresh all cached data (channels and target resolutions).
        """
        await self.get_channels(force_refresh=True)
        self.invalidate_all_resolutions()
