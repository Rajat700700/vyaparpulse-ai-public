"""'Prove it' share links for verified recoveries.

Endpoints
    POST   /api/impact-ledger/{recovery_id}/share          (authenticated)
    POST   /api/impact-ledger/{recovery_id}/share/revoke   (authenticated)
    GET    /api/public/proof/{token}                       (no auth)

The public proof endpoint returns ONLY the audit fields the judge needs to
verify a recovery — never the raw transaction table, other opportunities,
credentials or private masters.
"""
from __future__ import annotations
from datetime import datetime
from typing import Optional
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..db import get_db
from ..security import get_current_user
from ..services.share_tokens import (
    issue_share_token, verify_share_token, revoke_share_token,
    ShareTokenInvalid,
)


router = APIRouter(tags=["share"])


def _serialize(doc: dict) -> dict:
    out = {}
    for k, v in doc.items():
        if k == "_id":
            out["id"] = str(v)
        elif isinstance(v, ObjectId):
            out[k] = str(v)
        elif isinstance(v, datetime):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


class ShareIssueBody(BaseModel):
    ttl_days: Optional[int] = None


@router.post("/api/impact-ledger/{recovery_id}/share")
async def issue_share(recovery_id: str, body: ShareIssueBody = ShareIssueBody(),
                       current: dict = Depends(get_current_user)):
    db = get_db()
    try:
        rid = ObjectId(recovery_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid recovery id")
    ent = ObjectId(current["enterprise_id"])
    rec = await db.recoveries.find_one({"_id": rid, "enterprise_id": ent})
    if not rec:
        raise HTTPException(status_code=404, detail="Recovery not found in this enterprise")
    issued = issue_share_token(
        recovery_id=str(rid), enterprise_id=str(ent),
        issued_by=current.get("email", "system"),
        ttl_days=body.ttl_days,
    )
    # Persist an audit record on the recovery
    await db.recoveries.update_one(
        {"_id": rid},
        {"$push": {"share_tokens": {
            "jti": issued["jti"], "expires_at": issued["expires_at"],
            "issued_by": current.get("email", "system"),
            "issued_at": datetime.utcnow(),
        }}},
    )
    return {
        "token": issued["token"],
        "jti": issued["jti"],
        "expires_at": issued["expires_at"].isoformat(),
    }


class RevokeBody(BaseModel):
    jti: str


@router.post("/api/impact-ledger/{recovery_id}/share/revoke")
async def revoke_share(recovery_id: str, body: RevokeBody,
                        current: dict = Depends(get_current_user)):
    db = get_db()
    try:
        rid = ObjectId(recovery_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid recovery id")
    ent = ObjectId(current["enterprise_id"])
    rec = await db.recoveries.find_one({"_id": rid, "enterprise_id": ent})
    if not rec:
        raise HTTPException(status_code=404, detail="Recovery not found in this enterprise")
    # Ensure the jti was issued for this recovery
    if not any((t.get("jti") == body.jti) for t in (rec.get("share_tokens") or [])):
        raise HTTPException(status_code=404, detail="Token not issued for this recovery")
    await revoke_share_token(body.jti, revoked_by=current.get("email", "system"))
    return {"revoked": True, "jti": body.jti}


@router.get("/api/public/proof/{token}")
async def public_proof(token: str):
    """Public read-only audit view. No auth. Only returns the mandated audit
    fields for the pinned recovery; never surfaces unrelated data."""
    try:
        payload = await verify_share_token(token)
    except ShareTokenInvalid as e:
        raise HTTPException(status_code=401, detail=f"Share link invalid: {e}")
    db = get_db()
    try:
        rid = ObjectId(payload["rid"])
        ent = ObjectId(payload["ent"])
    except InvalidId:
        raise HTTPException(status_code=400, detail="Malformed token payload")

    rec = await db.recoveries.find_one({"_id": rid, "enterprise_id": ent})
    if not rec:
        raise HTTPException(status_code=404, detail="Recovery no longer available")

    # Pull the parent action for assigned_at / completed_at (attribution window).
    act = None
    if rec.get("action_id"):
        act = await db.actions.find_one({"_id": rec["action_id"], "enterprise_id": ent})

    # Enterprise display name (safe: name only, no secrets)
    entdoc = await db.enterprises.find_one({"_id": ent}, {"name": 1, "is_demo": 1})

    verified = int(rec.get("verified_paise") or 0)
    claimed = int(rec.get("claimed_paise") or 0)
    invoice_net = int(rec.get("invoice_net_paise") or 0)

    audit = {
        "enterprise": {
            "name": (entdoc or {}).get("name"),
            "is_demo": bool((entdoc or {}).get("is_demo", False)),
        },
        "outlet_code": rec.get("outlet_code"),
        "outlet_name": rec.get("outlet_name"),
        "distributor_code": rec.get("distributor_code"),
        "salesperson_code": rec.get("salesperson_code"),
        "salesperson_name": rec.get("salesperson_name"),
        "opportunity_type": rec.get("opportunity_type"),
        "action_id": str(rec.get("action_id")) if rec.get("action_id") else None,
        "invoice_no": rec.get("invoice_no"),
        "invoice_order_date": rec.get("invoice_order_date").isoformat()
            if isinstance(rec.get("invoice_order_date"), datetime) else rec.get("invoice_order_date"),
        "claimed_paise": claimed,
        "invoice_net_paise": invoice_net,
        "verified_paise": verified,
        "attribution_window": {
            "assigned_at": act.get("assigned_at").isoformat()
                if act and isinstance(act.get("assigned_at"), datetime) else None,
            "completed_at": act.get("completed_at").isoformat()
                if act and isinstance(act.get("completed_at"), datetime) else None,
            "window_end_note": "assigned_at ≤ invoice.order_date ≤ completed_at + 14 calendar days (inclusive)",
        },
        "calculation_explanation": (
            f"verified_paise = min(claimed {claimed}, invoice_net {invoice_net}) = {verified}. "
            f"Unique per (enterprise, distributor, outlet, invoice_no)."
        ),
        "token": {
            "jti": payload["jti"],
            "issued_at": datetime.utcfromtimestamp(payload["iat"]).isoformat() + "Z"
                if isinstance(payload.get("iat"), (int, float))
                else (payload["iat"].isoformat() if hasattr(payload["iat"], "isoformat") else None),
            "expires_at": datetime.utcfromtimestamp(payload["exp"]).isoformat() + "Z"
                if isinstance(payload.get("exp"), (int, float))
                else (payload["exp"].isoformat() if hasattr(payload["exp"], "isoformat") else None),
        },
    }
    return audit
