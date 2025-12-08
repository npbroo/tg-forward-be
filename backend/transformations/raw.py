"""
Raw transformation - passes message text through unchanged.

Useful when you want to forward messages exactly as received.
"""
from typing import Optional


class RawTransformation:
    """Pass message text through without modification."""

    name = "raw"
    description = "Forward message text exactly as received"

    def __call__(self, text: str) -> Optional[str]:
        """
        Return the text unchanged.

        Args:
            text: Message text to forward

        Returns:
            The original text, or None if text is empty
        """
        text = (text or "").strip()
        if not text:
            return None

        return text


# Create singleton instance for registration
raw_transform = RawTransformation()
