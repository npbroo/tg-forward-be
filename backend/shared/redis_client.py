import json
import redis.asyncio as redis
from config import settings

# Create a global async Redis client
redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

async def redis_set_json(key: str, value: dict):
    await redis_client.set(key, json.dumps(value))

async def redis_get_json(key: str):
    data = await redis_client.get(key)
    if data is None:
        return None
    return json.loads(data)

async def redis_scan_json(pattern: str):
    """
    Return list of JSON-decoded values for keys matching pattern (e.g. 'tg:session:*')
    """
    cursor = 0
    results: list[dict] = []
    while True:
        cursor, keys = await redis_client.scan(cursor=cursor, match=pattern, count=100)
        for k in keys:
            val = await redis_get_json(k)
            if val is not None:
                results.append(val)
        if cursor == 0:
            break
    return results
