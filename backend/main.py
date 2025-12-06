import asyncio
import contextlib
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware

from shared.redis_client import redis_get_json, redis_set_json
from config import settings
from routes import auth, dialogs, routing
from forwarder import run_forwarder


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """
    Lifespan context manager for FastAPI startup and shutdown events.
    """
    # Startup: Start the forwarder task
    forwarder_task = asyncio.create_task(run_forwarder())
    print("[STARTUP] Forwarder task started")

    yield

    # Shutdown: Cancel the forwarder task
    if forwarder_task and not forwarder_task.done():
        print("[SHUTDOWN] Cancelling forwarder task...")
        forwarder_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await forwarder_task
        print("[SHUTDOWN] Forwarder task stopped")


app = FastAPI(lifespan=lifespan)

# CORS middleware for frontend access
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


# Include routers
app.include_router(auth.router)
app.include_router(dialogs.router)
app.include_router(routing.router)