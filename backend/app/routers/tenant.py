"""Tenant-scoped read endpoints for Phase 1 shell (Command Centre)."""
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends
from bson import ObjectId

from ..db import get_db
from ..schemas import CommandCentreOut, EnterpriseOut, KPICards
from ..security import get_current_user
from ..services.recovery_engine import dedupe_topline


router = APIRouter(prefix="/api/tenant", tags=["tenant"])


@router.get("/command-centre", response_model=CommandCentreOut)
async def command_centre(current: dict = Depends(get_current_user)) -> CommandCentreOut:
    db = get_db()
    enterprise_id = current["enterprise_id"]
    ent_oid = ObjectId(enterprise_id)
    ent = await db.enterprises.find_one({"_id": ent_oid})

    latest = await db.import_batches.find(
        {"enterprise_id": ent_oid, "status": "completed"}
    ).sort("finished_at", -1).limit(1).to_list(1)

    analysis_as_of = None
    revenue_mtd = 0
    outlets_at_risk = 0
    estimated_opportunity = 0
    verified_recovery = 0

    if latest:
        v = latest[0].get("analysis_as_of")
        if hasattr(v, "isoformat"):
            analysis_as_of = v
        else:
            analysis_as_of = datetime.fromisoformat(str(v).replace("Z", "+00:00")) if v else None

        if analysis_as_of:
            month_start = analysis_as_of.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            pipeline = [
                {"$match": {"enterprise_id": ent_oid, "order_date": {"$gte": month_start, "$lte": analysis_as_of}}},
                {"$group": {"_id": None, "s": {"$sum": "$net_sales_paise"}}},
            ]
            agg = await db.transactions.aggregate(pipeline).to_list(1)
            revenue_mtd = int(agg[0]["s"]) if agg else 0

        opps = await db.opportunities.find({"enterprise_id": ent_oid}).to_list(None)
        outlets_at_risk = len({(o["distributor_code"], o["outlet_code"]) for o in opps
                               if o["type"] in ("LAPSED", "DECLINING")})
        estimated_opportunity = dedupe_topline(opps)
        # Verified recovery from the ledger (invoice-attributed only).
        rec_agg = await db.recoveries.aggregate([
            {"$match": {"enterprise_id": ent_oid, "verification_status": "VERIFIED"}},
            {"$group": {"_id": None, "sum": {"$sum": "$verified_paise"}}},
        ]).to_list(1)
        verified_recovery = int(rec_agg[0]["sum"]) if rec_agg else 0

    kpis = KPICards(
        revenue_mtd_paise=revenue_mtd,
        outlets_at_risk=outlets_at_risk,
        estimated_opportunity_paise=estimated_opportunity,
        verified_recovery_paise=verified_recovery,
    )
    enterprise = EnterpriseOut(
        id=enterprise_id,
        name=ent["name"] if ent else "Enterprise",
        is_demo=bool(ent.get("is_demo", False)) if ent else False,
        analysis_as_of=analysis_as_of,
    )
    is_empty = latest is None or revenue_mtd == 0 and estimated_opportunity == 0
    empty_reason = (
        "This is a safe interactive sandbox. Committing imports is disabled; production Recovery Radar data will be shown here in the pre-computed contest demo (Phase 3)."
        if enterprise.is_demo and is_empty
        else "No data imported yet. Upload sales data to see live recovery opportunities."
        if is_empty
        else ""
    )
    return CommandCentreOut(
        enterprise=enterprise, kpis=kpis, data_through=analysis_as_of,
        is_empty=is_empty, empty_reason=empty_reason,
    )
