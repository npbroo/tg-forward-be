from fastapi import FastAPI, Header, HTTPException, Depends

from shared.redis_client import redis_get_json, redis_set_json
from config import settings
from routes import auth, dialogs

app = FastAPI()


def require_admin(x_admin_token: str = Header(..., alias="X-Admin-Token")):
    if x_admin_token != settings.ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid admin token")
    return True

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/protected")
async def protected(_: bool = require_admin):
    return {"message": "You are authorized"}

@app.get("/redis-test")
async def redis_test(_: bool = Depends(require_admin)):
    """
    Simple Redis round-trip test.
    Writes a key and reads it back.
    """
    key = "test:hello"
    value = {"msg": "world"}

    await redis_set_json(key, value)
    read_back = await redis_get_json(key)

    return {"written": value, "read_back": read_back}


# Include auth routes
app.include_router(auth.router)
app.include_router(dialogs.router)