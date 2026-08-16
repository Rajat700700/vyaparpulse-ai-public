"""Actions + Recoveries + Ledger + Outlets router (Phase 3)."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Optional
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..db import get_db
from ..security import get_current_user, require_persistent_write, ROLE_DEMO
from ..services.attribution import verify_recovery, recovery_key
from ..services.state_machine import (
    transition_action, InvalidTransition, RequiresSkipReason,
)

router = APIRouter(prefix="/api", tags=["phase3"])


def _oid(x: str) -> ObjectId:
    return ObjectId(x)


def _serialize(doc: dict) -> dict:
    d = dict(doc)
    if "_id" in d:
        d["id"] = str(d.pop("_id"))
    for k, v in list(d.items()):
        if isinstance(v, ObjectId):
            d[k] = str(v)
        elif isinstance(v, datetime):
            d[k] = v.isoformat()
    return d


# ---------------- OUTLETS ----------------

@router.get("/outlets")
async def list_outlets(current: dict = Depends(get_current_user),
                       q: Optional[str] = None,
                       distributor: Optional[str] = None,
                       salesperson: Optional[str] = None,
                       beat: Optional[str] = None,
                       region: Optional[str] = None,
                       limit: int = 500):
    db = get_db()
    ent = _oid(current["enterprise_id"])

    pipeline = [
        {"$match": {"enterprise_id": ent, **({"distributor_code": distributor} if distributor else {}),
                    **({"salesperson_code": salesperson} if salesperson else {}),
                    **({"beat_or_route": beat} if beat else {}),
                    **({"region": region} if region else {})}},
        {"$group": {
            "_id": {"dist": "$distributor_code", "outlet": "$outlet_code"},
            "outlet_name": {"$last": "$outlet_name"},
            "distributor_code": {"$last": "$distributor_code"},
            "salesperson_code": {"$last": "$salesperson_code"},
            "salesperson_name": {"$last": "$salesperson_name"},
            "beat_or_route": {"$last": "$beat_or_route"},
            "region": {"$last": "$region"},
            "last_order_date": {"$max": "$order_date"},
            "net_180d_paise": {"$sum": "$net_sales_paise"},
            "orders": {"$sum": 1},
        }},
        {"$limit": int(limit)},
    ]
    rows = await db.transactions.aggregate(pipeline).to_list(None)
    for r in rows:
        gid = r.pop("_id", None) or {}
        r["outlet_code"] = gid.get("outlet")
        if r.get("last_order_date") and isinstance(r["last_order_date"], datetime):
            r["last_order_date"] = r["last_order_date"].isoformat()
    if q:
        ql = q.lower()
        rows = [r for r in rows if ql in (r.get("outlet_name") or "").lower()
                or ql in (r.get("distributor_code") or "").lower()]
    return {"count": len(rows), "outlets": rows}


@router.get("/outlets/{outlet_code}")
async def outlet_detail(outlet_code: str, current: dict = Depends(get_current_user),
                        distributor: Optional[str] = None):
    db = get_db()
    ent = _oid(current["enterprise_id"])
    filt = {"enterprise_id": ent, "outlet_code": outlet_code}
    if distributor: filt["distributor_code"] = distributor

    txs = await db.transactions.find(filt).sort("order_date", -1).limit(500).to_list(500)
    if not txs:
        raise HTTPException(status_code=404, detail="Outlet not found in this enterprise")

    meta = {
        "outlet_code": outlet_code,
        "outlet_name": txs[0].get("outlet_name"),
        "distributor_code": txs[0].get("distributor_code"),
        "salesperson_code": txs[0].get("salesperson_code"),
        "salesperson_name": txs[0].get("salesperson_name"),
        "beat_or_route": txs[0].get("beat_or_route"),
        "region": txs[0].get("region"),
    }

    # 6-month trend (buckets of 30 days)
    latest_batch = await db.import_batches.find(
        {"enterprise_id": ent, "status": "completed"}
    ).sort("finished_at", -1).limit(1).to_list(1)
    as_of = latest_batch[0]["analysis_as_of"] if latest_batch else datetime.now(timezone.utc)
    if isinstance(as_of, str):
        as_of = datetime.fromisoformat(as_of.replace("Z", "+00:00"))
    # Normalize to naive UTC to match tx order_date (which is stored tz-naive)
    if as_of.tzinfo is not None:
        as_of = as_of.astimezone(timezone.utc).replace(tzinfo=None)

    # 6-month trend (calendar-month buckets so labels never duplicate/skip)
    def _month_start(d):
        return d.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    def _month_end(d):
        # first day of next month
        if d.month == 12:
            return d.replace(year=d.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        return d.replace(month=d.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)

    trend = []
    cur_start = _month_start(as_of)
    for m in range(5, -1, -1):
        # walk back m months from as_of's month
        y = cur_start.year
        mo = cur_start.month - m
        while mo <= 0:
            mo += 12
            y -= 1
        m_start = cur_start.replace(year=y, month=mo)
        m_end = _month_end(m_start)
        s = sum((t.get("net_sales_paise") or 0) for t in txs
                if m_start <= (t["order_date"] if isinstance(t["order_date"], datetime)
                               else datetime.fromisoformat(t["order_date"])) < m_end)
        trend.append({"month_end": m_start.strftime("%b %Y"), "net_paise": int(s)})

    # SKU mix (top 8 last 90d)
    mix_map = {}
    cutoff = as_of - timedelta(days=90)
    for t in txs:
        od = t["order_date"] if isinstance(t["order_date"], datetime) else datetime.fromisoformat(t["order_date"])
        if od < cutoff: continue
        k = t["sku_code"]
        mix_map.setdefault(k, {"sku_code": k, "sku_name": t.get("sku_name"),
                               "category": t.get("category"), "net_paise": 0, "quantity": 0})
        mix_map[k]["net_paise"] += int(t.get("net_sales_paise") or 0)
        mix_map[k]["quantity"] += int(t.get("quantity") or 0)
    mix = sorted(mix_map.values(), key=lambda x: -x["net_paise"])[:8]

    # Order cadence
    dates = sorted({(t["order_date"] if isinstance(t["order_date"], datetime)
                     else datetime.fromisoformat(t["order_date"])).date() for t in txs})
    from statistics import median
    intervals = [(dates[i+1] - dates[i]).days for i in range(len(dates) - 1)]
    cadence = {
        "orders_lifetime": len(dates),
        "last_order_date": dates[-1].isoformat() if dates else None,
        "median_interval_days": int(median(intervals)) if intervals else None,
    }

    # Opportunities for this outlet
    opps = await db.opportunities.find({"enterprise_id": ent, "outlet_code": outlet_code}).to_list(None)
    opps = [_serialize(o) for o in opps]

    # Actions + recoveries
    acts = await db.actions.find({"enterprise_id": ent, "outlet_code": outlet_code})\
        .sort("assigned_at", -1).to_list(None)
    recs = await db.recoveries.find({"enterprise_id": ent, "outlet_code": outlet_code})\
        .sort("created_at", -1).to_list(None)

    return {
        "meta": meta,
        "as_of": as_of.isoformat(),
        "trend_6m": trend,
        "sku_mix": mix,
        "cadence": cadence,
        "opportunities": opps,
        "actions": [_serialize(a) for a in acts],
        "recoveries": [_serialize(r) for r in recs],
    }


# ---------------- ACTIONS ----------------

class AssignBody(BaseModel):
    opportunity_id: str
    salesperson_code: str
    due_date: Optional[datetime] = None
    notes: Optional[str] = None


class TransitionBody(BaseModel):
    event: str  # start | complete | skip
    invoice_ref: Optional[str] = None
    claimed_paise: Optional[int] = None
    skip_reason: Optional[str] = None
    notes: Optional[str] = None


def _is_demo(current) -> bool:
    return current.get("role") == ROLE_DEMO or current.get("is_demo")


def _demo_ttl_meta():
    exp = datetime.now(timezone.utc) + timedelta(hours=2)
    return {"is_demo_ephemeral": True, "expires_at": exp}


@router.post("/actions/assign")
async def assign_action(body: AssignBody, current: dict = Depends(get_current_user)):
    db = get_db()
    ent = _oid(current["enterprise_id"])
    opp = await db.opportunities.find_one({"_id": _oid(body.opportunity_id), "enterprise_id": ent})
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found in this enterprise")
    doc = {
        "enterprise_id": ent,
        "opportunity_id": _oid(body.opportunity_id),
        "opportunity_type": opp["type"],
        "distributor_code": opp["distributor_code"],
        "outlet_code": opp["outlet_code"],
        "outlet_name": opp.get("outlet_name"),
        "salesperson_code": body.salesperson_code,
        "salesperson_name": opp.get("salesperson_name"),
        "assigned_by": current["email"],
        "assigned_at": datetime.now(timezone.utc),
        "due_date": body.due_date or (datetime.now(timezone.utc) + timedelta(days=3)),
        "status": "ASSIGNED",
        "recommended_action": opp.get("recommended_action"),
        "est_recovery_paise_snapshot": opp.get("est_recovery_paise"),
        "priority_score_snapshot": opp.get("priority_score"),
        "notes": body.notes,
    }
    if _is_demo(current):
        doc.update(_demo_ttl_meta())
    r = await db.actions.insert_one(doc)
    return _serialize({**doc, "_id": r.inserted_id})


@router.get("/actions")
async def list_actions(current: dict = Depends(get_current_user),
                       salesperson: Optional[str] = None,
                       status: Optional[str] = None):
    db = get_db()
    ent = _oid(current["enterprise_id"])
    filt = {"enterprise_id": ent}
    if salesperson: filt["salesperson_code"] = salesperson
    if status: filt["status"] = status.upper()
    docs = await db.actions.find(filt).sort("due_date", 1).limit(500).to_list(500)

    # Bucket: today / overdue / upcoming (for salesperson view)
    now = datetime.now(timezone.utc)
    today_end = now.replace(hour=23, minute=59, second=59)
    today_start = now.replace(hour=0, minute=0, second=0)
    buckets = {"overdue": [], "today": [], "upcoming": [], "done": []}
    out = []
    for d in docs:
        s = _serialize(d)
        due = d.get("due_date")
        if isinstance(due, str):
            due = datetime.fromisoformat(due.replace("Z", "+00:00"))
        if isinstance(due, datetime) and due.tzinfo is None:
            due = due.replace(tzinfo=timezone.utc)
        if d["status"] in ("COMPLETED", "SKIPPED"):
            buckets["done"].append(s)
        elif due and due < today_start:
            buckets["overdue"].append(s)
        elif due and today_start <= due <= today_end:
            buckets["today"].append(s)
        else:
            buckets["upcoming"].append(s)
        out.append(s)
    return {"count": len(out), "actions": out, "buckets": buckets}


@router.post("/actions/{action_id}/transition")
async def transition(action_id: str, body: TransitionBody,
                     current: dict = Depends(get_current_user)):
    db = get_db()
    ent = _oid(current["enterprise_id"])
    doc = await db.actions.find_one({"_id": _oid(action_id), "enterprise_id": ent})
    if not doc:
        raise HTTPException(status_code=404, detail="Action not found in this enterprise")
    try:
        updated = transition_action(
            doc, body.event, by=current["email"],
            invoice_ref=body.invoice_ref, claimed_paise=body.claimed_paise,
            skip_reason=body.skip_reason, notes=body.notes,
        )
    except RequiresSkipReason as e:
        raise HTTPException(status_code=400, detail=str(e))
    except InvalidTransition as e:
        raise HTTPException(status_code=400, detail=str(e))

    # If COMPLETED with invoice_ref → run attribution and upsert recovery.
    recovery_out = None
    if updated["status"] == "COMPLETED" and updated.get("invoice_ref"):
        invoices = await db.transactions.find({
            "enterprise_id": ent,
            "distributor_code": updated["distributor_code"],
            "outlet_code": updated["outlet_code"],
            "invoice_no": updated["invoice_ref"],
        }).to_list(20)
        r = verify_recovery(
            invoices=invoices, invoice_no=updated["invoice_ref"],
            enterprise_id=str(ent), distributor_code=updated["distributor_code"],
            outlet_code=updated["outlet_code"],
            assigned_at=updated["assigned_at"], completed_at=updated["completed_at"],
            claimed_paise=int(updated.get("claimed_paise") or 0),
        )
        updated["verified_paise"] = r.verified_paise
        updated["verification_status"] = r.status

        if r.status == "VERIFIED":
            # Look up the parent opportunity for the full audit trail
            # (Phase 3 QA correction #6 — every recovery must expose
            # opportunity_type, salesperson_code, salesperson_name, action_id).
            opp_doc = None
            if doc.get("opportunity_id"):
                opp_doc = await db.opportunities.find_one({
                    "_id": doc["opportunity_id"], "enterprise_id": ent,
                })
            rec_doc = {
                "enterprise_id": ent,
                "action_id": doc["_id"],
                "opportunity_id": doc.get("opportunity_id"),
                "opportunity_type": (opp_doc or {}).get("type") or doc.get("opportunity_type"),
                "distributor_code": updated["distributor_code"],
                "outlet_code": updated["outlet_code"],
                "outlet_name": updated.get("outlet_name"),
                "salesperson_code": doc.get("salesperson_code"),
                "salesperson_name": (opp_doc or {}).get("salesperson_name") or doc.get("salesperson_name"),
                "invoice_no": updated["invoice_ref"],
                "invoice_order_date": r.invoice_order_date,
                "invoice_net_paise": r.invoice_net_paise,
                "claimed_paise": int(updated.get("claimed_paise") or 0),
                "verified_paise": r.verified_paise,
                "verification_status": "VERIFIED",
                "created_at": datetime.now(timezone.utc),
            }
            if _is_demo(current):
                rec_doc.update(_demo_ttl_meta())
            try:
                await db.recoveries.insert_one(rec_doc)
                recovery_out = _serialize(rec_doc)
            except Exception:
                # unique index prevented duplicate — return existing
                existing = await db.recoveries.find_one({
                    "enterprise_id": ent,
                    "distributor_code": updated["distributor_code"],
                    "outlet_code": updated["outlet_code"],
                    "invoice_no": updated["invoice_ref"],
                })
                recovery_out = _serialize(existing) if existing else None

    # Persist action update
    await db.actions.update_one({"_id": doc["_id"]}, {"$set": {k: v for k, v in updated.items() if k != "_id"}})
    return {"action": _serialize({**updated, "_id": doc["_id"]}), "recovery": recovery_out}


# ---------------- IMPACT LEDGER ----------------

@router.get("/impact-ledger")
async def impact_ledger(current: dict = Depends(get_current_user)):
    db = get_db()
    ent = _oid(current["enterprise_id"])

    # Estimated opportunity value — use the SAME deduped total that Command
    # Centre exposes (LAPSED > DECLINING > MISSED > WHITESPACE per outlet)
    # so the two KPIs reconcile exactly. Also expose the gross (undeduped) sum
    # for auditors who want to see it.
    opps_docs = await db.opportunities.find({"enterprise_id": ent}).to_list(None)
    estimated_count = len(opps_docs)
    estimated_paise = 0
    gross_paise = 0
    if opps_docs:
        from ..services.recovery_engine import dedupe_topline
        estimated_paise = dedupe_topline(opps_docs)
        gross_paise = sum(int(o.get("est_recovery_paise") or 0) for o in opps_docs)

    act_agg = await db.actions.aggregate([
        {"$match": {"enterprise_id": ent}},
        {"$group": {"_id": "$status", "n": {"$sum": 1},
                    "sum": {"$sum": "$est_recovery_paise_snapshot"}}},
    ]).to_list(None)
    a_counts = {a["_id"]: a["n"] for a in act_agg}
    assigned_count = sum(a_counts.get(s, 0) for s in ("ASSIGNED", "IN_PROGRESS"))
    completed_count = a_counts.get("COMPLETED", 0)

    rec_agg = await db.recoveries.aggregate([
        {"$match": {"enterprise_id": ent}},
        {"$group": {"_id": "$verification_status", "n": {"$sum": 1},
                    "sum": {"$sum": "$verified_paise"}}},
    ]).to_list(None)
    verified_paise = 0
    verified_count = 0
    for r in rec_agg:
        if r["_id"] == "VERIFIED":
            verified_paise = int(r["sum"])
            verified_count = int(r["n"])

    ledger = await db.recoveries.find({"enterprise_id": ent}).sort("created_at", -1).limit(200).to_list(200)
    return {
        "stages": {
            "estimated": {"count": estimated_count, "paise": estimated_paise,
                          "gross_paise": gross_paise,
                          "definition": "Deduped by precedence LAPSED > DECLINING > MISSED > WHITESPACE per outlet — matches Command Centre. Gross shows the undeduped sum."},
            "assigned": {"count": assigned_count},
            "completed": {"count": completed_count},
            "verified": {"count": verified_count, "paise": verified_paise,
                         "definition": "Only invoice-attributed recoveries within [assigned_at, completed_at + 14d]; capped at invoice value; unique per (enterprise, distributor, outlet, invoice_no)."},
        },
        "entries": [_serialize(r) for r in ledger],
    }


# ---------------- DEMO RESET ----------------

@router.post("/demo/reset")
async def demo_reset(current: dict = Depends(get_current_user)):
    if not _is_demo(current):
        raise HTTPException(status_code=403, detail="Only demo sessions may reset")
    db = get_db()
    ent = _oid(current["enterprise_id"])
    ac = await db.actions.delete_many({"enterprise_id": ent, "is_demo_ephemeral": True})
    rc = await db.recoveries.delete_many({"enterprise_id": ent, "is_demo_ephemeral": True})
    return {"actions_deleted": ac.deleted_count, "recoveries_deleted": rc.deleted_count}
