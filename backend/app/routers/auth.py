"""Authenticated user endpoints (login, logout, me, refresh)."""
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from bson import ObjectId

from ..db import get_db
from ..schemas import LoginRequest, MessageOut, UserOut
from ..security import (
    check_brute_force,
    clear_attempts,
    clear_auth_cookies,
    create_access_token,
    create_refresh_token,
    get_current_user,
    record_failed_attempt,
    set_auth_cookies,
    verify_password,
    decode_token,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=UserOut)
async def login(payload: LoginRequest, request: Request, response: Response) -> UserOut:
    email = payload.email.lower().strip()
    client_ip = request.client.host if request.client else "unknown"
    identifier = f"{client_ip}:{email}"

    await check_brute_force(identifier)

    db = get_db()
    user = await db.users.find_one({"email": email})
    if not user or not user.get("is_active", True):
        await record_failed_attempt(identifier)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    # Demo users cannot log in with password
    if user.get("is_demo"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Use the sandbox demo entry instead")

    if not verify_password(payload.password, user["password_hash"]):
        await record_failed_attempt(identifier)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    await clear_attempts(identifier)

    user_id = str(user["_id"])
    enterprise_id = str(user["enterprise_id"])

    enterprise = await db.enterprises.find_one({"_id": ObjectId(enterprise_id)})
    enterprise_name = enterprise["name"] if enterprise else None

    access = create_access_token(user_id, email, user["role"], enterprise_id, is_demo=False)
    refresh = create_refresh_token(user_id)
    set_auth_cookies(response, access, refresh, is_demo=False)

    return UserOut(
        id=user_id, email=email, role=user["role"], enterprise_id=enterprise_id,
        enterprise_name=enterprise_name, is_demo=False,
        display_name=user.get("display_name"),
        access_token=access,
    )


@router.post("/logout", response_model=MessageOut)
async def logout(response: Response, current: dict = Depends(get_current_user)) -> MessageOut:
    clear_auth_cookies(response)
    return MessageOut(message="Logged out")


@router.get("/me", response_model=UserOut)
async def me(current: dict = Depends(get_current_user)) -> UserOut:
    db = get_db()
    enterprise = await db.enterprises.find_one({"_id": ObjectId(current["enterprise_id"])})
    return UserOut(
        id=current["id"], email=current["email"], role=current["role"],
        enterprise_id=current["enterprise_id"],
        enterprise_name=enterprise["name"] if enterprise else None,
        is_demo=bool(current.get("is_demo", False)),
        display_name=current.get("display_name"),
    )


@router.post("/refresh", response_model=MessageOut)
async def refresh(request: Request, response: Response) -> MessageOut:
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="Missing refresh token")
    import jwt as _jwt
    try:
        payload = decode_token(token)
    except _jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token expired")
    except _jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")

    db = get_db()
    user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
    if not user or not user.get("is_active", True):
        raise HTTPException(status_code=401, detail="User not found")

    access = create_access_token(
        str(user["_id"]), user["email"], user["role"],
        str(user["enterprise_id"]), is_demo=bool(user.get("is_demo", False)),
    )
    set_auth_cookies(response, access, is_demo=bool(user.get("is_demo", False)))
    return MessageOut(message="Refreshed")
