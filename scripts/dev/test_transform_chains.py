#!/usr/bin/env python3
"""
Test transformation chaining functionality.
"""
import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent.parent.parent / "backend"
sys.path.insert(0, str(backend_dir.parent))

from backend.transformations import transform_message


def test_single_transformation():
    """Test single transformation (backward compatible)."""
    print("\n=== Test Single Transformation ===")

    text = "Check out this token: EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"

    result = transform_message(text, "solana_ca")
    print(f"Input: {text}")
    print(f"Transform: solana_ca")
    print(f"Output: {result}")

    assert result == "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", "Single transformation failed"
    print("✅ PASS\n")


def test_transformation_chain():
    """Test chaining multiple transformations."""
    print("=== Test Transformation Chain ===")

    # Example: Extract raw text (pass-through for testing)
    text = "Check out $BTC and $ETH today! Visit https://example.com"

    # Chain: raw (pass-through)
    result = transform_message(text, ["raw"])
    print(f"Input: {text}")
    print(f"Chain: ['raw']")
    print(f"Output: {result}")
    assert result == text, "Single-item chain failed"
    print("✅ PASS\n")


def test_chain_stops_on_none():
    """Test that chain stops when transformation returns None."""
    print("=== Test Chain Stops on None ===")

    text = "This has no Solana address"

    # Chain: solana_ca (returns None) -> url (should not run)
    result = transform_message(text, ["solana_ca", "url"])
    print(f"Input: {text}")
    print(f"Chain: ['solana_ca', 'url']")
    print(f"Output: {result}")
    assert result is None, "Chain should stop when first transform returns None"
    print("✅ PASS\n")


def test_real_world_chain():
    """Test a realistic transformation chain."""
    print("=== Test Real-World Chain ===")

    # Scenario: First extract URL, then pass it through raw
    text = "Amazing project! Check it out: https://example.com/token $BTC"

    # Extract URL first
    result = transform_message(text, ["url"])
    print(f"Input: {text}")
    print(f"Chain: ['url']")
    print(f"Output: {result}")
    assert result == "https://example.com/token", "URL extraction failed"
    print("✅ PASS\n")

    # Now try ticker extraction
    result = transform_message(text, ["ticker"])
    print(f"Input: {text}")
    print(f"Chain: ['ticker']")
    print(f"Output: {result}")
    assert result == "$BTC", "Ticker extraction failed"
    print("✅ PASS\n")


def test_empty_chain():
    """Test empty chain fallback."""
    print("=== Test Empty Chain ===")

    text = "Hello world"

    result = transform_message(text, [])
    print(f"Input: {text}")
    print(f"Chain: []")
    print(f"Output: {result}")
    assert result == "Hello world", "Empty chain should return trimmed text"
    print("✅ PASS\n")


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("TRANSFORMATION CHAINING TESTS")
    print("="*60)

    try:
        test_single_transformation()
        test_transformation_chain()
        test_chain_stops_on_none()
        test_real_world_chain()
        test_empty_chain()

        print("="*60)
        print("ALL TESTS PASSED ✅")
        print("="*60 + "\n")
        return 0

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}\n")
        return 1
    except Exception as e:
        print(f"\n❌ ERROR: {e}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
