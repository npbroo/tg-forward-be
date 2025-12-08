"""
Solana Contract Address (CA) transformation.

Extracts and validates Solana contract addresses from message text.
"""
import re
from typing import Optional

try:
    from solders.pubkey import Pubkey
    SOLANA_AVAILABLE = True
except ImportError:
    SOLANA_AVAILABLE = False
    print("Warning: solders not installed. Solana address validation will be disabled.")


# Solana address regex - matches base58 strings of 32-44 characters
CA_REGEX = re.compile(r"(?<![1-9A-HJ-NP-Za-km-z])([1-9A-HJ-NP-Za-km-z]{32,44})(?![1-9A-HJ-NP-Za-km-z])")


def is_valid_solana_address(ca: str) -> bool:
    """Validate if a string is a valid Solana address."""
    if not SOLANA_AVAILABLE:
        # If solders is not available, do basic validation
        return len(ca) >= 32 and len(ca) <= 44

    try:
        Pubkey.from_string(ca)
        return True
    except ValueError:
        return False


class SolanaCATransformation:
    """Extract and validate Solana contract address from text."""

    name = "solana_ca"
    description = "Extract and validate Solana contract addresses from message text"

    def __call__(self, text: str) -> Optional[str]:
        """
        Extract the first valid Solana contract address from text.

        Args:
            text: Message text to search

        Returns:
            First valid Solana address found, or None if no valid address
        """
        text = (text or "").strip()
        if not text:
            return None

        candidates = CA_REGEX.findall(text)
        for ca in candidates:
            if is_valid_solana_address(ca):
                return ca

        return None


# Create singleton instance for registration
solana_ca_transform = SolanaCATransformation()
