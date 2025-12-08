# Transformation Chaining

The Telegram forwarder now supports **transformation chaining** - the ability to apply multiple transformations to a message in sequence.

## Overview

Transformation chains allow you to:
1. Apply multiple transformations in order
2. Process the output of one transformation as input to the next
3. Stop the chain if any transformation returns `None`
4. Create complex message processing pipelines

## How It Works

When a transformation chain is applied:
1. The first transformation receives the original message text
2. Each subsequent transformation receives the output of the previous one
3. If any transformation returns `None`, the chain stops and no message is forwarded
4. The final output is forwarded to the target chat

## Database Schema Changes

The `Route` model now includes an optional `transformChain` field:

```prisma
model Route {
  id               String   @id @default(uuid())
  routeId          String   @unique
  sourceChat       String
  targetChat       String
  transformType    String   @default("solana_ca")  // Primary/first transformation
  transformChain   String?  @db.Text                // JSON array of transformations
  enabled          Boolean  @default(true)
  userId           String
  user             User     @relation(fields: [userId], references: [id], onDelete: Cascade)
}
```

## API Usage

### Creating a Route with a Single Transformation (Backward Compatible)

```bash
POST /api/routes
{
  "source_chat": "source_channel_id",
  "target_chat": "target_channel_id",
  "transform_type": "solana_ca",
  "enabled": true
}
```

### Creating a Route with a Transformation Chain

```bash
POST /api/routes
{
  "source_chat": "source_channel_id",
  "target_chat": "target_channel_id",
  "transform_type": ["url", "raw"],  // Array of transformations
  "enabled": true
}
```

### Updating a Route's Transformation Chain

```bash
PATCH /api/routes/{route_id}
{
  "transform_type": ["ticker", "raw"]  // Update to a chain
}
```

Or update back to a single transformation:

```bash
PATCH /api/routes/{route_id}
{
  "transform_type": "solana_ca"  // Single transformation
}
```

## Examples

### Example 1: URL Then Raw

Extract URL and forward it as-is:

```json
{
  "transform_type": ["url"]
}
```

**Input:** `"Check out https://example.com for more info"`
**Output:** `"https://example.com"`

### Example 2: Filter Then Process

First check if there's a Solana address, then extract it:

```json
{
  "transform_type": ["solana_ca"]
}
```

**Input:** `"New token: EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v buy now!"`
**Output:** `"EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"`

**Input:** `"No token address here"`
**Output:** `None` (message not forwarded)

### Example 3: Multiple Extractors

You could create a custom transformation that combines multiple extractors:

```json
{
  "transform_type": ["ticker"]
}
```

**Input:** `"$BTC and $ETH are trending!"`
**Output:** `"$BTC $ETH"`

## Programmatic Usage

### Python

```python
from backend.transformations import transform_message

# Single transformation
result = transform_message("text", "solana_ca")

# Transformation chain
result = transform_message("text", ["url", "raw"])

# Empty chain (returns trimmed text)
result = transform_message("text", [])
```

### In Route Models

```python
from backend.core.models import RouteCreateRequest

# Single transformation
route = RouteCreateRequest(
    source_chat="123",
    target_chat="456",
    transform_type="solana_ca"
)

# Transformation chain
route = RouteCreateRequest(
    source_chat="123",
    target_chat="456",
    transform_type=["url", "ticker"]
)
```

## Use Cases

### 1. URL Extraction with Validation

Chain: `["url"]`

- **Use case:** Forward only URLs from a news channel
- **Input:** `"Breaking news! Read more at https://news.com/article"`
- **Output:** `"https://news.com/article"`

### 2. Ticker Symbol Extraction

Chain: `["ticker"]`

- **Use case:** Monitor financial channels and extract ticker symbols
- **Input:** `"$AAPL hit new highs! Also watching $MSFT"`
- **Output:** `"$AAPL $MSFT"`

### 3. Solana Address Extraction

Chain: `["solana_ca"]`

- **Use case:** Monitor crypto channels for new token addresses
- **Input:** `"New gem: 7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU"`
- **Output:** `"7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU"`

### 4. Pass-Through with Filtering

Chain: `["raw"]`

- **Use case:** Forward all non-empty messages
- **Input:** `"Any text message"`
- **Output:** `"Any text message"`

## Best Practices

1. **Keep chains short**: Aim for 1-3 transformations max for performance
2. **Order matters**: Place more restrictive transformations first to fail fast
3. **Test thoroughly**: Test chains with various message formats
4. **Document your chains**: Add comments explaining complex transformation logic
5. **Use single transformations when possible**: Only use chains when truly needed

## Chain Behavior

### Stopping on None

If any transformation in the chain returns `None`, the entire chain stops and no message is forwarded:

```python
# Chain: ["solana_ca", "url"]
# Input: "No Solana address here"
# solana_ca returns None → chain stops → no message forwarded
```

### Empty Chains

An empty chain `[]` acts as a pass-through, returning the trimmed input text:

```python
transform_message("  hello  ", [])  # Returns "hello"
```

### Single-Item Chains

A single-item chain `["transform"]` is functionally equivalent to using that transformation directly:

```python
transform_message("text", ["url"])  # Same as transform_message("text", "url")
```

## Migration Guide

### Migrating from Single Transformations

If you have existing routes with single transformations, they will continue to work without any changes. The API is backward compatible.

### Upgrading to Chains

To upgrade an existing route to use a chain:

```bash
# Before (single transformation)
{
  "transform_type": "solana_ca"
}

# After (transformation chain)
{
  "transform_type": ["solana_ca"]  # Wrap in array
}
```

### Database Migration

Run the Prisma migration to add the `transformChain` column:

```bash
# Generate migration
prisma migrate dev --name add_transformation_chains

# Or apply existing migration
prisma migrate deploy
```

## Troubleshooting

**Chain not working:**
- Verify all transformation names in the chain are registered
- Check that each transformation returns a value before the next one runs
- Use the test script to debug: `python scripts/dev/test_transform_chains.py`

**API rejecting chain:**
- Ensure you're passing an array: `["url"]` not `"url"`
- Check that transformation names are strings
- Verify JSON formatting is correct

**Route showing wrong transformation:**
- The API returns the full chain in `transform_type`
- Check both `transformType` (primary) and `transformChain` (full chain) in database

## Testing

Test your transformation chains:

```bash
source .venv/bin/activate
python scripts/dev/test_transform_chains.py
```

## Performance Considerations

- **Chain length**: Each transformation adds processing time
- **Early termination**: Chains stop at the first `None`, improving performance
- **Database**: `transformChain` is stored as JSON TEXT, add indexes if querying frequently

## Future Enhancements

Potential future features:
- Conditional branching in chains
- Parallel transformation execution
- Chain validation on creation
- Chain performance metrics
- Chain templates/presets
