# Message Transformations

This folder contains modular message transformation plugins for the Telegram forwarder.

## Overview

Transformations allow you to process and extract specific content from messages before forwarding them. Each transformation is a self-contained module that can be easily added, removed, or modified.

## Built-in Transformations

### 1. `raw` - Raw Text
- **File**: `raw.py`
- **Description**: Forwards message text exactly as received
- **Use case**: When you want to forward entire messages without modification

### 2. `solana_ca` - Solana Contract Address Extractor
- **File**: `solana_ca.py`
- **Description**: Extracts and validates Solana contract addresses from message text
- **Use case**: Monitoring crypto channels and forwarding only valid contract addresses

### 3. `url` - URL Extractor
- **File**: `url_extractor.py`
- **Description**: Extracts the first URL found in message text
- **Use case**: Forwarding only URLs from news channels or link aggregators

## Creating a New Transformation

Follow these steps to add a custom transformation:

### 1. Create a New File

Create a new Python file in this directory, e.g., `my_transform.py`:

```python
"""
My Custom Transformation.

Brief description of what this transformation does.
"""
from typing import Optional


class MyTransformation:
    """Your transformation class."""

    # Unique name for this transformation (used in database)
    name = "my_transform"

    # User-friendly description
    description = "Brief description of what this does"

    def __call__(self, text: str) -> Optional[str]:
        """
        Transform the input text.

        Args:
            text: The message text to transform

        Returns:
            Transformed text, or None if transformation doesn't apply
        """
        text = (text or "").strip()
        if not text:
            return None

        # Your transformation logic here
        transformed = text.upper()  # Example: convert to uppercase

        return transformed


# Create singleton instance for registration
my_transform = MyTransformation()
```

### 2. Register the Transformation

Edit `registry.py` and add your transformation to the `_auto_register()` function:

```python
def _auto_register():
    """Automatically register all transformations in this module."""
    from .raw import raw_transform
    from .solana_ca import solana_ca_transform
    from .url_extractor import url_extractor_transform
    from .my_transform import my_transform  # Add this line

    register_transformation(raw_transform)
    register_transformation(solana_ca_transform)
    register_transformation(url_extractor_transform)
    register_transformation(my_transform)  # Add this line
```

### 3. Restart the Application

The transformation will be automatically registered and available for use.

## Example Transformations

### Email Extractor

```python
import re
from typing import Optional

EMAIL_REGEX = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')

class EmailExtractorTransformation:
    name = "email"
    description = "Extract first email address from message text"

    def __call__(self, text: str) -> Optional[str]:
        text = (text or "").strip()
        if not text:
            return None

        match = EMAIL_REGEX.search(text)
        return match.group(0) if match else None

email_extractor_transform = EmailExtractorTransformation()
```

### Hashtag Collector

```python
from typing import Optional

class HashtagCollectorTransformation:
    name = "hashtags"
    description = "Extract all hashtags and combine them"

    def __call__(self, text: str) -> Optional[str]:
        text = (text or "").strip()
        if not text:
            return None

        hashtags = [word for word in text.split() if word.startswith('#')]
        return ' '.join(hashtags) if hashtags else None

hashtag_collector_transform = HashtagCollectorTransformation()
```

### Price Extractor

```python
import re
from typing import Optional

PRICE_REGEX = re.compile(r'\$[\d,]+\.?\d*')

class PriceExtractorTransformation:
    name = "price"
    description = "Extract price information from message text"

    def __call__(self, text: str) -> Optional[str]:
        text = (text or "").strip()
        if not text:
            return None

        prices = PRICE_REGEX.findall(text)
        return ', '.join(prices) if prices else None

price_extractor_transform = PriceExtractorTransformation()
```

## Using Transformations

When creating a route via the API, specify the transformation type:

```json
{
  "source_chat": "source_channel_id",
  "target_chat": "target_channel_id",
  "transform_type": "solana_ca",
  "enabled": true
}
```

## Best Practices

1. **Return None for no match**: If your transformation doesn't find what it's looking for, return `None` to skip forwarding
2. **Validate input**: Always check if text is empty or None before processing
3. **Use clear names**: Choose descriptive, unique names for your transformations
4. **Add documentation**: Include docstrings explaining what your transformation does
5. **Test thoroughly**: Test with various message formats before deploying

## Troubleshooting

- **Transformation not found**: Make sure you registered it in `registry.py`
- **Import errors**: Check that your file is in the `transformations` directory
- **Not working**: Verify the transformation name in the database matches the `name` attribute
