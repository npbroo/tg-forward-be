#!/usr/bin/env python3
"""
Test the transformation system with sample messages.
"""
import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent.parent.parent / "backend"
sys.path.insert(0, str(backend_dir.parent))

from backend.transformations import transform_message, list_transformations


def test_transformations():
    """Test all registered transformations with sample inputs."""

    print("\n" + "="*60)
    print("TRANSFORMATION SYSTEM TEST")
    print("="*60)

    # List all available transformations
    transformations = list_transformations()
    print(f"\n📋 Available Transformations ({len(transformations)}):\n")
    for name, description in transformations.items():
        print(f"  • {name}: {description}")

    print("\n" + "="*60)
    print("TESTING TRANSFORMATIONS")
    print("="*60)

    # Test cases
    test_cases = [
        # Raw transformation
        {
            "input": "Hello, this is a test message!",
            "transform": "raw",
            "expected": "Hello, this is a test message!"
        },
        # Solana CA transformation
        {
            "input": "Check out this token: EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
            "transform": "solana_ca",
            "expected": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
        },
        {
            "input": "Invalid address here: 123abc",
            "transform": "solana_ca",
            "expected": None
        },
        # URL transformation
        {
            "input": "Visit our website at https://example.com for more info",
            "transform": "url",
            "expected": "https://example.com"
        },
        {
            "input": "No URL in this message",
            "transform": "url",
            "expected": None
        },
        # Edge cases
        {
            "input": "",
            "transform": "raw",
            "expected": None
        },
        {
            "input": "   ",
            "transform": "raw",
            "expected": None
        },
    ]

    passed = 0
    failed = 0

    for i, test in enumerate(test_cases, 1):
        input_text = test["input"]
        transform_type = test["transform"]
        expected = test["expected"]

        print(f"\n[Test {i}] Transform: {transform_type}")
        print(f"  Input: {repr(input_text[:50])}")

        result = transform_message(input_text, transform_type)

        print(f"  Output: {repr(result)}")
        print(f"  Expected: {repr(expected)}")

        if result == expected:
            print("  ✅ PASS")
            passed += 1
        else:
            print("  ❌ FAIL")
            failed += 1

    print("\n" + "="*60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("="*60 + "\n")

    return failed == 0


if __name__ == "__main__":
    success = test_transformations()
    sys.exit(0 if success else 1)
