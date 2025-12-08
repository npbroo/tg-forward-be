"""
Transformation registry system.

Automatically discovers and registers all transformations in the transformations folder.
"""
from typing import Dict, Optional, Callable
from .base import Transformation


class TransformationRegistry:
    """Registry for message transformations."""

    def __init__(self):
        self._transformations: Dict[str, Transformation] = {}

    def register(self, transformation: Transformation) -> None:
        """
        Register a transformation.

        Args:
            transformation: Transformation instance to register
        """
        name = transformation.name
        if name in self._transformations:
            print(f"Warning: Transformation '{name}' is already registered. Overwriting.")

        self._transformations[name] = transformation
        print(f"[TRANSFORM] Registered transformation: {name} - {transformation.description}")

    def get(self, name: str) -> Optional[Transformation]:
        """
        Get a transformation by name.

        Args:
            name: Name of the transformation

        Returns:
            Transformation instance, or None if not found
        """
        return self._transformations.get(name)

    def transform(self, text: str, transform_type: str) -> Optional[str]:
        """
        Apply a transformation to text.

        Args:
            text: Text to transform
            transform_type: Name of the transformation to apply

        Returns:
            Transformed text, or None if transformation not found or doesn't apply
        """
        transformation = self.get(transform_type)
        if not transformation:
            print(f"Warning: Transformation '{transform_type}' not found. Falling back to raw.")
            return text.strip() if text else None

        return transformation(text)

    def transform_chain(self, text: str, transform_types: list[str]) -> Optional[str]:
        """
        Apply a chain of transformations to text.

        Each transformation in the chain receives the output of the previous one.
        If any transformation returns None, the chain stops and returns None.

        Args:
            text: Initial text to transform
            transform_types: List of transformation names to apply in order

        Returns:
            Final transformed text, or None if any transformation returns None
        """
        if not transform_types:
            return text.strip() if text else None

        current_text = text
        for i, transform_name in enumerate(transform_types):
            transformation = self.get(transform_name)
            if not transformation:
                print(f"Warning: Transformation '{transform_name}' at position {i} not found. Stopping chain.")
                return None

            current_text = transformation(current_text)
            if current_text is None:
                # Transformation returned None, stop the chain
                return None

        return current_text

    def list_transformations(self) -> Dict[str, str]:
        """
        List all registered transformations.

        Returns:
            Dictionary mapping transformation names to descriptions
        """
        return {
            name: transform.description
            for name, transform in self._transformations.items()
        }


# Global registry instance
_registry = TransformationRegistry()


def register_transformation(transformation: Transformation) -> None:
    """Register a transformation with the global registry."""
    _registry.register(transformation)


def get_transformation(name: str) -> Optional[Transformation]:
    """Get a transformation from the global registry."""
    return _registry.get(name)


def transform_message(text: str, transform_type: str | list[str]) -> Optional[str]:
    """
    Apply a transformation or chain of transformations using the global registry.

    Args:
        text: Text to transform
        transform_type: Single transformation name or list of transformation names

    Returns:
        Transformed text, or None if transformation doesn't apply
    """
    if isinstance(transform_type, list):
        return _registry.transform_chain(text, transform_type)
    return _registry.transform(text, transform_type)


def list_transformations() -> Dict[str, str]:
    """List all registered transformations."""
    return _registry.list_transformations()


# Auto-register built-in transformations
def _auto_register():
    """Automatically register all transformations in this module."""
    from .raw import raw_transform
    from .solana_ca import solana_ca_transform
    from .url_extractor import url_extractor_transform
    from .ticker_symbol import ticker_symbol_transform
    from .gembot_conservative import gembot_conservative_transform
    from .gembot_balanced import gembot_balanced_transform
    from .gembot_risky import gembot_risky_transform

    register_transformation(raw_transform)
    register_transformation(solana_ca_transform)
    register_transformation(url_extractor_transform)
    register_transformation(ticker_symbol_transform)
    register_transformation(gembot_conservative_transform)
    register_transformation(gembot_balanced_transform)
    register_transformation(gembot_risky_transform)


# Run auto-registration on import
_auto_register()
