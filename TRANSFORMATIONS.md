# Message Transformation System

The Telegram forwarder now supports a modular, plugin-based transformation system that allows you to easily create custom message processing logic.

## Quick Start

### Viewing Available Transformations

**Via API:**
```bash
GET /api/routes/transformations
```

**Via Python:**
```python
from backend.transformations import list_transformations

transformations = list_transformations()
for name, description in transformations.items():
    print(f"{name}: {description}")
```

### Using Transformations in Routes

When creating or updating a route, specify the `transform_type`:

```bash
POST /api/routes
{
  "source_chat": "source_channel_id",
  "target_chat": "target_channel_id",
  "transform_type": "solana_ca",  # Use any registered transformation
  "enabled": true
}
```

## Built-in Transformations

### 1. `raw` - Raw Text Forwarding
Forwards messages exactly as received without any processing.

**Example:**
- Input: `"Hello, this is a test message!"`
- Output: `"Hello, this is a test message!"`

### 2. `solana_ca` - Solana Contract Address Extractor
Extracts and validates Solana contract addresses from message text.

**Example:**
- Input: `"Check out this token: EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"`
- Output: `"EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"`

### 3. `url` - URL Extractor
Extracts the first URL found in message text.

**Example:**
- Input: `"Visit our website at https://example.com for more info"`
- Output: `"https://example.com"`

### 4. `ticker` - Ticker Symbol Extractor
Extracts stock/crypto ticker symbols (e.g., $BTC, $ETH).

**Example:**
- Input: `"Check out $BTC and $ETH today!"`
- Output: `"$BTC $ETH"`

## Creating Custom Transformations

### Step 1: Create Your Transformation File

Create a new file in `backend/transformations/`, for example `my_transform.py`:

```python
"""
My Custom Transformation.

Brief description of what this transformation does.
"""
from typing import Optional


class MyTransformation:
    """Your transformation class."""

    # Unique name (used in API and database)
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

        # Your custom logic here
        transformed = text.upper()  # Example: convert to uppercase

        return transformed


# Create singleton instance
my_transform = MyTransformation()
```

### Step 2: Register Your Transformation

Edit `backend/transformations/registry.py` and add your transformation to `_auto_register()`:

```python
def _auto_register():
    """Automatically register all transformations in this module."""
    from .raw import raw_transform
    from .solana_ca import solana_ca_transform
    from .url_extractor import url_extractor_transform
    from .ticker_symbol import ticker_symbol_transform
    from .my_transform import my_transform  # Add this

    register_transformation(raw_transform)
    register_transformation(solana_ca_transform)
    register_transformation(url_extractor_transform)
    register_transformation(ticker_symbol_transform)
    register_transformation(my_transform)  # Add this
```

### Step 3: Restart the Application

Your transformation will be automatically registered and available for use!

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

### Price Filter

```python
import re
from typing import Optional

PRICE_REGEX = re.compile(r'\$[\d,]+\.?\d*')

class PriceExtractorTransformation:
    name = "price"
    description = "Extract all prices from message text"

    def __call__(self, text: str) -> Optional[str]:
        text = (text or "").strip()
        if not text:
            return None

        prices = PRICE_REGEX.findall(text)
        return ', '.join(prices) if prices else None

price_extractor_transform = PriceExtractorTransformation()
```

### Hashtag Collector

```python
from typing import Optional

class HashtagCollectorTransformation:
    name = "hashtags"
    description = "Extract all hashtags from message text"

    def __call__(self, text: str) -> Optional[str]:
        text = (text or "").strip()
        if not text:
            return None

        hashtags = [word for word in text.split() if word.startswith('#')]
        return ' '.join(hashtags) if hashtags else None

hashtag_collector_transform = HashtagCollectorTransformation()
```

## Best Practices

1. **Return `None` for no match**: If your transformation doesn't find what it's looking for, return `None` to skip forwarding that message
2. **Validate input**: Always check if text is empty or None before processing
3. **Use descriptive names**: Choose clear, unique names for your transformations
4. **Document your code**: Add docstrings explaining what your transformation does
5. **Test thoroughly**: Test with various message formats before deploying
6. **Keep it simple**: Each transformation should do one thing well
7. **Use regex carefully**: Test your regex patterns with multiple inputs

## Testing Your Transformation

Use the test script:

```bash
source .venv/bin/activate
python scripts/dev/test_transformations.py
```

Or test programmatically:

```python
from backend.transformations import transform_message

result = transform_message("Test message", "my_transform")
print(result)
```

## Architecture

```
backend/transformations/
├── __init__.py           # Package exports
├── base.py               # Transformation protocol/interface
├── registry.py           # Registration and discovery system
├── raw.py                # Raw text transformation
├── solana_ca.py          # Solana CA extractor
├── url_extractor.py      # URL extractor
├── ticker_symbol.py      # Ticker symbol extractor
└── README.md             # Detailed documentation
```

## How It Works

1. **Registration**: When the application starts, all transformations are auto-registered in the global registry
2. **Message Handling**: When a message is received, the forwarder looks up the route's `transform_type`
3. **Transformation**: The appropriate transformation is applied to the message text
4. **Forwarding**: If the transformation returns a non-None value, it's forwarded to the target chat

## API Reference

### List Transformations
```
GET /api/routes/transformations
```

Returns:
```json
{
  "raw": "Forward message text exactly as received",
  "solana_ca": "Extract and validate Solana contract addresses from message text",
  "url": "Extract and forward the first URL found in message text",
  "ticker": "Extract stock/crypto ticker symbols (e.g., $BTC, $AAPL)"
}
```

### Create Route with Transformation
```
POST /api/routes
{
  "source_chat": "source_id",
  "target_chat": "target_id",
  "transform_type": "solana_ca",
  "enabled": true
}
```

### Update Route Transformation
```
PATCH /api/routes/{route_id}
{
  "transform_type": "url"
}
```

## Troubleshooting

**Transformation not found:**
- Check that you registered it in `registry.py`
- Verify the transformation name matches exactly

**Import errors:**
- Ensure your file is in the `backend/transformations/` directory
- Check for syntax errors in your transformation file

**Transformation not working:**
- Verify the `name` attribute matches what's in the database
- Check that your `__call__` method returns `Optional[str]`
- Test with the test script to debug

## Future Enhancements

Potential future features:
- Hot-reloading of transformations without restart
- Chaining multiple transformations
- Transformation parameters/configuration
- Async transformations for API calls
- Transformation metrics and analytics
