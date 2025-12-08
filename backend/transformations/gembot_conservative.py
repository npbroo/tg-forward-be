"""
GemBot Conservative Filter transformation.

Only allows messages through if they contain the 💎 (gem/diamond) emoji.
The entire message is forwarded unchanged if it contains the emoji.
"""
from typing import Optional


class GemBotConservativeTransformation:
    """Filter messages that contain the 💎 emoji."""

    name = "gembot_conservative"
    description = "Only forward messages containing the 💎 emoji (unchanged)"

    def __call__(self, text: str) -> Optional[str]:
        """
        Check if message contains 💎 emoji and return unchanged if it does.

        Args:
            text: Message text to check

        Returns:
            Original text if it contains 💎, None otherwise
        """
        text = (text or "").strip()
        if not text:
            return None

        # Check if the message contains the diamond emoji
        if "💎" in text:
            return text

        # No diamond emoji found, filter out this message
        return None


# Create singleton instance for registration
gembot_conservative_transform = GemBotConservativeTransformation()
