"""Idempotent seed for admin user + demo tenant.

Phase 1 responsibility:
- Ensure one production enterprise + one Enterprise Admin.
- Ensure one demo enterprise flagged is_demo=True with a DEMO user.
- Ensure enterprise_settings exist for both, holding default thresholds.
"""
import os
from datetime import datetime, timezone
from pathlib import Path

from .db import get_db
from .security import (
    ROLE_DEMO,
    ROLE_ENTERPRISE_ADMIN,
    hash_password,
    verify_password,
)

DEFAULT_SETTINGS = {
    "lapsed_no_order_days": 30,
    "lapsed_prior_orders_min": 2,
    "lapsed_prior_window_days": 90,
    "decline_pct": 0.25,
    "decline_window_days": 30,
    "missed_multiplier": 1.5,
    "whitespace_peer_pct": 0.4,
    "calc_version": "v1.0.0",
}


async def _upsert_enterprise(name: str, is_demo: bool) -> str:
    db = get_db()
    existing = await db.enterprises.find_one({"name": name})
    now = datetime.now(timezone.utc)
    if existing:
        return str(existing["_id"])
    result = await db.enterprises.insert_one(
        {"name": name, "is_demo": is_demo, "currency": "INR", "created_at": now}
    )
    return str(result.inserted_id)


async def _upsert_settings(enterprise_id) -> None:
    db = get_db()
    from bson import ObjectId
    await db.enterprise_settings.update_one(
        {"enterprise_id": ObjectId(enterprise_id)},
        {
            "$setOnInsert": {
                "enterprise_id": ObjectId(enterprise_id),
                "created_at": datetime.now(timezone.utc),
                **DEFAULT_SETTINGS,
            }
        },
        upsert=True,
    )


async def _upsert_user(email: str, password: str, role: str, enterprise_id: str,
                      display_name: str, is_demo: bool = False) -> str:
    db = get_db()
    from bson import ObjectId
    existing = await db.users.find_one({"email": email})
    now = datetime.now(timezone.utc)
    if existing is None:
        result = await db.users.insert_one({
            "email": email,
            "password_hash": hash_password(password),
            "role": role,
            "enterprise_id": ObjectId(enterprise_id),
            "display_name": display_name,
            "is_active": True,
            "is_demo": is_demo,
            "created_at": now,
        })
        return str(result.inserted_id)
    # keep password in sync with env for admin convenience
    if not verify_password(password, existing["password_hash"]):
        await db.users.update_one(
            {"_id": existing["_id"]},
            {"$set": {"password_hash": hash_password(password)}},
        )
    # normalise enterprise linkage if missing
    if existing.get("enterprise_id") != ObjectId(enterprise_id):
        await db.users.update_one(
            {"_id": existing["_id"]},
            {"$set": {"enterprise_id": ObjectId(enterprise_id), "role": role, "is_demo": is_demo}},
        )
    return str(existing["_id"])


async def seed_all() -> dict:
    admin_email = os.environ["ADMIN_EMAIL"]
    admin_password = os.environ["ADMIN_PASSWORD"]
    demo_name = os.environ["DEMO_ENTERPRISE_NAME"]\n    demo_password = os.environ["DEMO_USER_PASSWORD"]

    # Production enterprise (contest pilot tenant)
    prod_ent_id = await _upsert_enterprise("VyaparPulse Pilot Enterprise", is_demo=False)
    await _upsert_settings(prod_ent_id)
    admin_id = await _upsert_user(
        admin_email, admin_password, ROLE_ENTERPRISE_ADMIN, prod_ent_id,
        "Enterprise Admin", is_demo=False,
    )

    # Demo tenant (interactive sandbox)
    demo_ent_id = await _upsert_enterprise(demo_name, is_demo=True)
    await _upsert_settings(demo_ent_id)
    demo_user_id = await _upsert_user(
        "sandbox@vyaparpulse.ai", demo_password, ROLE_DEMO, demo_ent_id,
        "Sandbox Demo User", is_demo=True,
    )

    return {
        "admin_user_id": admin_id,
        "prod_enterprise_id": prod_ent_id,
        "demo_enterprise_id": demo_ent_id,
        "demo_user_id": demo_user_id,
    }

