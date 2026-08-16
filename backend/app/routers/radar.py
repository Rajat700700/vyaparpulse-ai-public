"""Recovery Radar API — opportunities list, filters, detail."""
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional

from ..db import get_db
from ..security import get_current_user
from ..services.recovery_engine import dedupe_topline

router = APIRouter(prefix="/api/radar", tags=["radar"])


def _serialize(o: dict) -> dict:
    o = dict(o)
    o["id"] = str(o.pop("_id"))
    o["enterprise_id"] = str(o["enterprise_id"])
    o.pop("import_batch_id", None)
    if o.get("analysis_as_of") and hasattr(o["analysis_as_of"], "isoformat"):
        o["analysis_as_of"] = o["analysis_as_of"].isoformat()
    if o.get("created_at") and hasattr(o["created_at"], "isoformat"):
        o["created_at"] = o["created_at"].isoformat()
    return o


@router.get("/opportunities")
async def list_opportunities(
    current: dict = Depends(get_current_user),
    type: Optional[str] = None,
    distributor: Optional[str] = None,
    salesperson: Optional[str] = None,
    beat: Optional[str] = None,
    region: Optional[str] = None,
    min_score: int = 0,
    q: Optional[str] = None,
    limit: int = Query(200, le=1000),
):
    db = get_db()
    filt = {"enterprise_id": ObjectId(current["enterprise_id"])}
    if type: filt["type"] = type.upper()
    if distributor: filt["distributor_code"] = distributor
    if salesperson: filt["salesperson_code"] = salesperson
    if beat: filt["beat_or_route"] = beat
    if region: filt["region"] = region
    if min_score: filt["priority_score"] = {"$gte": int(min_score)}
    if q:
        filt["$or"] = [
            {"outlet_name": {"$regex": q, "$options": "i"}},
            {"outlet_code": {"$regex": q, "$options": "i"}},
        ]
    cursor = db.opportunities.find(filt).sort("priority_score", -1).limit(limit)
    docs = [_serialize(d) async for d in cursor]
    return {"count": len(docs), "opportunities": docs}


@router.get("/summary")
async def summary(current: dict = Depends(get_current_user)):
    db = get_db()
    ent = ObjectId(current["enterprise_id"])
    all_opps = await db.opportunities.find({"enterprise_id": ent}).to_list(None)
    counts = {"LAPSED": 0, "DECLINING": 0, "MISSED": 0, "WHITESPACE": 0}
    for o in all_opps:
        counts[o["type"]] = counts.get(o["type"], 0) + 1
    priority_outlets = len({(o["distributor_code"], o["outlet_code"]) for o in all_opps if o["priority_score"] >= 60})
    recoverable = dedupe_topline(all_opps)

    # Distinct filter values
    distributors = sorted({o["distributor_code"] for o in all_opps if o.get("distributor_code")})
    salespeople = sorted({o["salesperson_code"] for o in all_opps if o.get("salesperson_code")})
    beats = sorted({o["beat_or_route"] for o in all_opps if o.get("beat_or_route")})
    regions = sorted({o["region"] for o in all_opps if o.get("region")})

    latest = await db.import_batches.find({"enterprise_id": ent, "status": "completed"})\
        .sort("finished_at", -1).limit(1).to_list(1)
    analysis_as_of = None
    if latest:
        v = latest[0].get("analysis_as_of")
        analysis_as_of = v.isoformat() if hasattr(v, "isoformat") else v

    return {
        "counts": counts,
        "priority_outlets": priority_outlets,
        "recoverable_paise": recoverable,
        "filters": {"distributors": distributors, "salespeople": salespeople,
                    "beats": beats, "regions": regions},
        "analysis_as_of": analysis_as_of,
    }
