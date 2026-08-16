"""Deterministic facts assembler for the AI Daily Recovery Brief.

The LLM never performs arithmetic — this module computes every ₹ and count.
The LLM receives a structured JSON facts dict and is asked ONLY to explain
and prioritise; it must not invent numbers.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from bson import ObjectId

from ..db import get_db
from .recovery_engine import dedupe_topline


BRIEF_VERSION = "brief-v1.0.0"


async def build_facts(enterprise_id: str) -> dict[str, Any]:
    """Return a JSON-serialisable dict of deterministic facts for the brief."""
    db = get_db()
    ent = ObjectId(enterprise_id)

    latest = await db.import_batches.find(
        {"enterprise_id": ent, "status": "completed"}
    ).sort("finished_at", -1).limit(1).to_list(1)
    analysis_as_of = latest[0]["analysis_as_of"] if latest else None
    if hasattr(analysis_as_of, "isoformat"):
        as_of_iso = analysis_as_of.isoformat()
    else:
        as_of_iso = None

    opps = await db.opportunities.find({"enterprise_id": ent}).to_list(None)
    total_opps = len(opps)
    est_deduped_paise = dedupe_topline(opps) if opps else 0

    # Top 5 opportunities by priority score
    top_priorities = sorted(opps, key=lambda o: -int(o.get("priority_score", 0)))[:5]
    top = []
    for o in top_priorities:
        top.append({
            "type": o.get("type"),
            "outlet_code": o.get("outlet_code"),
            "outlet_name": o.get("outlet_name"),
            "distributor_code": o.get("distributor_code"),
            "salesperson_code": o.get("salesperson_code"),
            "salesperson_name": o.get("salesperson_name"),
            "region": o.get("region"),
            "est_recovery_paise": int(o.get("est_recovery_paise") or 0),
            "priority_score": int(o.get("priority_score") or 0),
            "confidence": float(o.get("confidence") or 0),
            "reason": o.get("reason"),
            "recommended_action": o.get("recommended_action"),
        })

    # Risk counts by type
    by_type: dict[str, int] = defaultdict(int)
    by_type_paise: dict[str, int] = defaultdict(int)
    for o in opps:
        by_type[o.get("type", "?")] += 1
        by_type_paise[o.get("type", "?")] += int(o.get("est_recovery_paise") or 0)
    risks = [
        {"type": t, "count": by_type[t], "gross_paise": by_type_paise[t]}
        for t in ("LAPSED", "DECLINING", "MISSED", "WHITESPACE") if t in by_type
    ]

    # Salesperson workload — actions by salesperson (open only)
    sp_agg = await db.actions.aggregate([
        {"$match": {"enterprise_id": ent, "status": {"$in": ["ASSIGNED", "IN_PROGRESS"]}}},
        {"$group": {"_id": "$salesperson_code", "count": {"$sum": 1},
                    "sum_paise": {"$sum": "$est_recovery_paise_snapshot"}}},
        {"$sort": {"sum_paise": -1}},
        {"$limit": 5},
    ]).to_list(None)
    salesperson_actions = [
        {"salesperson_code": s["_id"], "open_actions": int(s["count"]),
         "open_est_paise": int(s.get("sum_paise") or 0)}
        for s in sp_agg
    ]

    # Verified recovery total (locked)
    rec_agg = await db.recoveries.aggregate([
        {"$match": {"enterprise_id": ent, "verification_status": "VERIFIED"}},
        {"$group": {"_id": None, "sum": {"$sum": "$verified_paise"}, "n": {"$sum": 1}}},
    ]).to_list(1)
    verified_paise = int(rec_agg[0]["sum"]) if rec_agg else 0
    verified_count = int(rec_agg[0]["n"]) if rec_agg else 0

    # Overdue actions count (past due, still open)
    now = datetime.now(timezone.utc)
    overdue = await db.actions.count_documents({
        "enterprise_id": ent,
        "status": {"$in": ["ASSIGNED", "IN_PROGRESS"]},
        "due_date": {"$lt": now},
    })

    return {
        "brief_version": BRIEF_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "analysis_as_of": as_of_iso,
        "summary_counts": {
            "total_opportunities": total_opps,
            "estimated_recovery_deduped_paise": est_deduped_paise,
            "verified_recovery_paise": verified_paise,
            "verified_recovery_count": verified_count,
            "overdue_actions": int(overdue),
        },
        "risks_by_type": risks,
        "top_priorities": top,
        "salesperson_workload": salesperson_actions,
    }
