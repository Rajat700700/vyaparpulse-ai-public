"""Sandbox demo entry — no login required.

Issues a short-lived DEMO token scoped to the demo enterprise. All persistent
write routes must depend on `require_persistent_write` so demo tokens are
rejected. Demo tokens permit temporary in-memory writes only.
"""
from fastapi import APIRouter, HTTPException, Response
from bson import ObjectId

from ..db import get_db
from ..schemas import UserOut
from ..security import ROLE_DEMO, create_access_token, set_auth_cookies

router = APIRouter(prefix="/api/demo", tags=["demo"])


@router.post("/session", response_model=UserOut)
async def start_sandbox(response: Response) -> UserOut:
    db = get_db()
    ent = await db.enterprises.find_one({"is_demo": True})
    if not ent:
        raise HTTPException(status_code=503, detail="Sandbox demo tenant not seeded")
    user = await db.users.find_one({"enterprise_id": ent["_id"], "role": ROLE_DEMO})
    if not user:
        raise HTTPException(status_code=503, detail="Sandbox demo user not seeded")

    user_id = str(user["_id"])
    enterprise_id = str(ent["_id"])
    token = create_access_token(
        user_id, user["email"], ROLE_DEMO, enterprise_id, is_demo=True,
    )
    set_auth_cookies(response, token, is_demo=True)
    return UserOut(
        id=user_id, email=user["email"], role=ROLE_DEMO,
        enterprise_id=enterprise_id, enterprise_name=ent["name"],
        is_demo=True, display_name=user.get("display_name"),
        access_token=token,
    )
