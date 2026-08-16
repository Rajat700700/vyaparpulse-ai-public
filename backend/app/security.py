"""Password hashing, JWT tokens, brute-force protection, tenant scope dependency."""
import os
from datetime import datetime, timezone, timedelta
from typing import Optional
import bcrypt
import jwt
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import Depends, HTTPException, Request, status

from .db import get_db

JWT_ALGORITHM = "HS256"

# Roles ---------------------------------------------------------------
ROLE_PLATFORM_ADMIN = "PLATFORM_ADMIN"
ROLE_ENTERPRISE_ADMIN = "ENTERPRISE_ADMIN"
ROLE_RSM = "RSM"
ROLE_DIST_MGR = "DIST_MGR"
ROLE_SALESPERSON = "SALESPERSON"
ROLE_DEMO = "DEMO"

ALL_ROLES = {
    ROLE_PLATFORM_ADMIN,
    ROLE_ENTERPRISE_ADMIN,
    ROLE_RSM,
    ROLE_DIST_MGR,
    ROLE_SALESPERSON,
    ROLE_DEMO,
}

# Password ------------------------------------------------------------
def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# JWT -----------------------------------------------------------------
def _secret() -> str:
    return os.environ["JWT_SECRET"]


def _access_minutes() -> int:
    return int(os.environ.get("ACCESS_TOKEN_MINUTES", "60"))


def _refresh_days() -> int:
    return int(os.environ.get("REFRESH_TOKEN_DAYS", "7"))


def _demo_minutes() -> int:
    return int(os.environ.get("DEMO_TOKEN_MINUTES", "120"))


def create_access_token(user_id: str, email: str, role: str, enterprise_id: str, is_demo: bool = False) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "enterprise_id": enterprise_id,
        "is_demo": is_demo,
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=_demo_minutes() if is_demo else _access_minutes()),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, _secret(), algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "type": "refresh",
        "exp": datetime.now(timezone.utc) + timedelta(days=_refresh_days()),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, _secret(), algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, _secret(), algorithms=[JWT_ALGORITHM])


def set_auth_cookies(response, access_token: str, refresh_token: Optional[str] = None, is_demo: bool = False) -> None:
    max_age = 60 * (_demo_minutes() if is_demo else _access_minutes())
    response.set_cookie(
        key="access_token", value=access_token, httponly=True, secure=True,
        samesite="none", max_age=max_age, path="/",
    )
    if refresh_token:
        response.set_cookie(
            key="refresh_token", value=refresh_token, httponly=True, secure=True,
            samesite="none", max_age=60 * 60 * 24 * _refresh_days(), path="/",
        )


def clear_auth_cookies(response) -> None:
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")


# Current user + tenant scope ----------------------------------------
async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

    db = get_db()
    try:
        user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
    except InvalidId:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid subject")
    if not user or not user.get("is_active", True):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    user["_id"] = str(user["_id"])
    user["id"] = user["_id"]
    user["enterprise_id"] = str(user.get("enterprise_id"))
    user.pop("password_hash", None)
    return user


def require_roles(*roles: str):
    async def _dep(current: dict = Depends(get_current_user)) -> dict:
        if current.get("role") not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return current
    return _dep


def require_persistent_write(current: dict = Depends(get_current_user)) -> dict:
    """Sandbox demo users may hold temporary in-memory state, but cannot
    mutate persistent production data. Any persistent-write route must depend
    on this guard.
    """
    if current.get("is_demo") or current.get("role") == ROLE_DEMO:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sandbox demo cannot modify persistent data",
        )
    return current


# Brute force ---------------------------------------------------------
MAX_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


async def check_brute_force(identifier: str) -> None:
    db = get_db()
    doc = await db.login_attempts.find_one({"identifier": identifier})
    if doc and doc.get("attempts", 0) >= MAX_ATTEMPTS:
        expires_at = doc.get("expires_at")
        if expires_at and expires_at > datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many failed attempts. Try again later.",
            )


async def record_failed_attempt(identifier: str) -> None:
    db = get_db()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_MINUTES)
    await db.login_attempts.update_one(
        {"identifier": identifier},
        {"$inc": {"attempts": 1}, "$set": {"expires_at": expires_at}},
        upsert=True,
    )


async def clear_attempts(identifier: str) -> None:
    db = get_db()
    await db.login_attempts.delete_one({"identifier": identifier})
