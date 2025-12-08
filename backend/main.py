import asyncio
import contextlib
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.database import connect_db, disconnect_db
from backend.api.routes import auth, dialogs, routing, users
from backend.services.forwarder import start_forwarder_manager, stop_forwarder_manager
from backend.auth import get_current_admin


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """
    Lifespan context manager for FastAPI startup and shutdown events.
    """
    # Startup: Connect to database
    print("[STARTUP] Connecting to database...")
    await connect_db()
    print("[STARTUP] Database connected")

    # Startup: Start the forwarder manager (spawns one worker per user)
    print("[STARTUP] Starting forwarder manager...")
    await start_forwarder_manager()
    print("[STARTUP] Forwarder manager started")

    yield

    # Shutdown: Stop the forwarder manager
    print("[SHUTDOWN] Stopping forwarder manager...")
    await stop_forwarder_manager()
    print("[SHUTDOWN] Forwarder manager stopped")

    # Shutdown: Disconnect from database
    print("[SHUTDOWN] Disconnecting from database...")
    await disconnect_db()
    print("[SHUTDOWN] Database disconnected")


app = FastAPI(lifespan=lifespan)

# CORS middleware for frontend access (allow all origins)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/protected")
async def protected(admin: str = Depends(get_current_admin)):
    return {"message": f"You are authorized as {admin}"}


# Include routers
app.include_router(auth.router)
app.include_router(dialogs.router)
app.include_router(routing.router)
app.include_router(users.router)
