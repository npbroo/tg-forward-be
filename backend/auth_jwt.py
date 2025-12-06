import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config import settings
from models import LoginRequest, LoginResponse


security = HTTPBearer()


class JWTDecodeError(Exception):
    pass


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64decode(data: str) -> bytes:
    padding = '=' * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _sign(message: bytes) -> bytes:
    if settings.JWT_ALGO != "HS256":
        raise ValueError("Only HS256 JWTs are supported")
    secret = settings.JWT_SECRET.encode("utf-8")
    return hmac.new(secret, message, hashlib.sha256).digest()


def encode_jwt(payload: Dict[str, Any]) -> str:
    header = {"alg": settings.JWT_ALGO, "typ": "JWT"}
    header_bytes = json.dumps(header, separators=(",", ":")).encode("utf-8")
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    header_segment = _b64encode(header_bytes)
    payload_segment = _b64encode(payload_bytes)
    signing_input = f"{header_segment}.{payload_segment}".encode("ascii")
    signature_segment = _b64encode(_sign(signing_input))
    return f"{header_segment}.{payload_segment}.{signature_segment}"


def decode_jwt(token: str) -> Dict[str, Any]:
    try:
        header_segment, payload_segment, signature_segment = token.split(".")
    except ValueError as exc:  # pragma: no cover - defensive
        raise JWTDecodeError("Malformed token") from exc

    try:
        header = json.loads(_b64decode(header_segment))
        payload = json.loads(_b64decode(payload_segment))
    except (json.JSONDecodeError, ValueError) as exc:
        raise JWTDecodeError("Invalid token encoding") from exc

    if header.get("alg") != settings.JWT_ALGO:
        raise JWTDecodeError("Unsupported algorithm")

    expected_signature = _b64encode(_sign(f"{header_segment}.{payload_segment}".encode("ascii")))
    if not hmac.compare_digest(signature_segment, expected_signature):
        raise JWTDecodeError("Invalid token signature")

    exp = payload.get("exp")
    if exp is not None:
        if not isinstance(exp, int):
            raise JWTDecodeError("Invalid exp claim")
        if datetime.now(timezone.utc).timestamp() >= exp:
            raise JWTDecodeError("Token expired")

    return payload


def create_access_token(subject: str, expires_minutes: int | None = None) -> str:
    """Create a signed JWT for the given subject."""
    if expires_minutes is None:
        expires_minutes = settings.JWT_EXPIRE_MINUTES

    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=expires_minutes)
    payload = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return encode_jwt(payload)


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """Validate the provided bearer token and return the admin username."""
    token = credentials.credentials
    try:
        payload = decode_jwt(token)
    except JWTDecodeError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        )

    subject = payload.get("sub")
    if subject != settings.ADMIN_USERNAME:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authorized",
        )

    return subject


async def login(body: LoginRequest) -> LoginResponse:
    """Validate credentials and return a JWT access token."""
    if (
        body.username != settings.ADMIN_USERNAME
        or body.password != settings.ADMIN_PASSWORD
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    token = create_access_token(subject=body.username)
    return LoginResponse(access_token=token)
