"""
Base transformation interface for message transformations.

Each transformation is a callable that takes a message text and returns
either a transformed string or None if the transformation doesn't apply.
"""
from typing import Optional, Protocol


class Transformation(Protocol):
    """Protocol defining the transformation interface."""

    name: str
    description: str

    def __call__(self, text: str) -> Optional[str]:
        """
        Transform the input text.

        Args:
            text: The message text to transform

        Returns:
            Transformed text, or None if transformation doesn't apply
        """
        ...
