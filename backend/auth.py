import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass

from fastapi import Cookie, HTTPException, status

COOKIE_NAME = "resumeforge_session"


@dataclass(frozen=True)
class User:
    id: str
    name: str
    email: str


def _configured_users() -> list[dict]:
    try:
        users = json.loads(os.getenv("AUTH_USERS_JSON", "[]"))
        return users if isinstance(users, list) else []
    except json.JSONDecodeError:
        return []


def authenticate(email: str, password: str) -> User | None:
    """Validate a login against the four deployment-secret credentials."""
    for record in _configured_users():
        email_match = hmac.compare_digest(str(record.get("email", "")).lower(), email.strip().lower())
        password_match = hmac.compare_digest(str(record.get("password", "")), password)
        if email_match and password_match:
            return User(id=str(record["id"]), name=str(record["name"]), email=str(record["email"]))
    return None


def _secret() -> bytes:
    secret = os.getenv("SESSION_SECRET", "")
    if len(secret) < 32:
        raise RuntimeError("SESSION_SECRET must contain at least 32 characters")
    return secret.encode("utf-8")


def create_session(user: User) -> str:
    """Create a signed seven-day stateless session token."""
    payload = json.dumps({"id": user.id, "name": user.name, "email": user.email, "exp": int(time.time()) + 604800}, separators=(",", ":")).encode()
    encoded = base64.urlsafe_b64encode(payload).rstrip(b"=")
    signature = hmac.new(_secret(), encoded, hashlib.sha256).digest()
    return f"{encoded.decode()}.{base64.urlsafe_b64encode(signature).rstrip(b'=').decode()}"


def read_session(token: str) -> User | None:
    """Validate and decode a stateless session token."""
    try:
        encoded, supplied_signature = token.split(".", 1)
        expected = hmac.new(_secret(), encoded.encode(), hashlib.sha256).digest()
        signature = base64.urlsafe_b64decode(supplied_signature + "=" * (-len(supplied_signature) % 4))
        if not hmac.compare_digest(expected, signature):
            return None
        payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
        if int(payload["exp"]) < int(time.time()):
            return None
        configured = next((item for item in _configured_users() if item.get("id") == payload.get("id")), None)
        if not configured:
            return None
        return User(id=payload["id"], name=payload["name"], email=payload["email"])
    except (ValueError, KeyError, json.JSONDecodeError, TypeError):
        return None


def require_user(resumeforge_session: str | None = Cookie(default=None)) -> User:
    """Require a valid ResumeForge session for a protected API route."""
    user = read_session(resumeforge_session or "")
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sign in to continue")
    return user
