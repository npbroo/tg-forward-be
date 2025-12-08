"""
Message transformation system.

This package provides a modular system for transforming messages before forwarding.
Supports both single transformations and chaining multiple transformations together.

To add a new transformation:
1. Create a new file in this directory (e.g., my_transform.py)
2. Define a class with `name` and `description` attributes
3. Implement __call__(self, text: str) -> Optional[str]
4. Create a singleton instance
5. Import and register it in registry.py's _auto_register() function

Example:
    # my_transform.py
    class MyTransformation:
        name = "my_transform"
        description = "My custom transformation"

        def __call__(self, text: str) -> Optional[str]:
            # Your transformation logic here
            return text.upper()

    my_transform = MyTransformation()

    # Then in registry.py, add to _auto_register():
    from .my_transform import my_transform
    register_transformation(my_transform)

Chaining transformations:
    # Single transformation
    result = transform_message("text", "solana_ca")

    # Chain of transformations (applied in order)
    result = transform_message("text", ["raw", "url"])
"""

from .base import Transformation
from .registry import (
    register_transformation,
    get_transformation,
    transform_message,
    list_transformations,
)

__all__ = [
    "Transformation",
    "register_transformation",
    "get_transformation",
    "transform_message",
    "list_transformations",
]
