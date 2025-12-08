"""
Ticker Symbol Extraction transformation.

Extracts stock/crypto ticker symbols from message text.
Example: "$BTC" or "$AAPL" - extracts the symbol after the dollar sign.
"""
import re
from typing import Optional


# Ticker symbol regex - matches $SYMBOL format (2-5 uppercase letters)
TICKER_REGEX = re.compile(r'\$([A-Z]{2,5})(?:\s|$|[^\w])')


class TickerSymbolTransformation:
    """Extract ticker symbols from message text."""

    name = "ticker"
    description = "Extract stock/crypto ticker symbols (e.g., $BTC, $AAPL)"

    def __call__(self, text: str) -> Optional[str]:
        """
        Extract all ticker symbols from text.

        Args:
            text: Message text to search

        Returns:
            Space-separated ticker symbols, or None if no tickers found
        """
        text = (text or "").strip()
        if not text:
            return None

        matches = TICKER_REGEX.findall(text)
        if matches:
            # Return all unique tickers found
            unique_tickers = list(dict.fromkeys(matches))  # Preserve order
            return ' '.join(f'${ticker}' for ticker in unique_tickers)

        return None


# Create singleton instance for registration
ticker_symbol_transform = TickerSymbolTransformation()
