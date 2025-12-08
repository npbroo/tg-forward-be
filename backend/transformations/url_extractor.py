"""
URL extraction transformation.

Extracts the first URL from message text.
Example use case: Forward only URLs from a news channel.
"""
import re
from typing import Optional


# Common URL regex pattern
URL_REGEX = re.compile(
    r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
)


class URLExtractorTransformation:
    """Extract the first URL from message text."""

    name = "url"
    description = "Extract and forward the first URL found in message text"

    def __call__(self, text: str) -> Optional[str]:
        """
        Extract the first URL from text.

        Args:
            text: Message text to search

        Returns:
            First URL found, or None if no URL present
        """
        text = (text or "").strip()
        if not text:
            return None

        match = URL_REGEX.search(text)
        if match:
            return match.group(0)

        return None


# Create singleton instance for registration
url_extractor_transform = URLExtractorTransformation()
