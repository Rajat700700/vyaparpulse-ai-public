"""Ingestion + Recovery Radar API routers."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional
from bson import ObjectId
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from ..db import get_db
from ..security import get_current_user, require_persistent_write
from ..services.ai_mapping import ai_map_headers_verbose
from ..services.ingest import file_hash, insert_rows, parse_file, validate_and_normalise
from ..services.mapping import REQUIRED, suggest_mapping
from ..services.recovery_engine import compute, dedupe_topline

router = APIRouter(prefix="/api/imports", tags=["imports"])


class PreviewOut(BaseModel):
    headers: list[str]
    sample: list[dict]
    mapping_suggestion: dict
    required_fields: list[str]
    file_hash: str
    ai_status: str = "skipped"  # "ok" | "unavailable" | "skipped"


@router.post("/preview", response_model=PreviewOut)
async def preview(file: UploadFile = File(...),
                  current: dict = Depends(get_current_user)):
    content = await file.read()
    try:
        df = parse_file(file.filename or "", content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    headers = list(df.columns)
    rules_map = suggest_mapping(headers)

    # AI fallback: rules-first at ≥0.85 wins. Anything else (unmapped or
    # rules-uncertain) is offered to GPT-5.2. AI output is validated against
    # the canonical allowlist and merged WITHOUT overriding high-confidence
    # rules. Timeout / provider failure surfaces via ai_status so the UI can
    # tell the user "AI unavailable — review manually" instead of pretending
    # everything is fine.
    confidently_mapped = {h for h, s in rules_map.items() if s["confidence"] >= 0.85}
    ai_candidates = [h for h in headers if h not in confidently_mapped]
    ai_map, ai_status = await ai_map_headers_verbose(ai_candidates)

    merged = dict(rules_map)
    for h, v in ai_map.items():
        prior = merged.get(h)
        # Never overwrite a rules-first (≥0.85) hit
        if prior is not None and prior.get("source") == "rules" and prior["confidence"] >= 0.85:
            continue
        # Prefer AI when its confidence exceeds the (uncertain) rules suggestion
        if prior is None or v["confidence"] > prior["confidence"]:
            merged[h] = v

    sample = df.head(20).astype(str).to_dict(orient="records")
    return PreviewOut(
        headers=headers, sample=sample,
        mapping_suggestion=merged,
        required_fields=REQUIRED, file_hash=file_hash(content),
        ai_status=ai_status,
    )


class ValidateIn(BaseModel):
    mapping: dict[str, str]  # source_header -> target_field


class ValidateOut(BaseModel):
    ok: bool
    blocking: list[str]
    warnings: list[str]
    stats: dict
    rejected_preview: list[dict]


class ImportOut(BaseModel):
    batch_id: str
    inserted: int
    duplicates: int
    stats: dict
    warnings: list[str]
    analysis_as_of: datetime


async def _read_and_parse(file: UploadFile):
    content = await file.read()
    df = parse_file(file.filename or "", content)
    return df, content


@router.post("/validate", response_model=ValidateOut)
async def validate(file: UploadFile = File(...),
                   mapping: str = Form(...),
                   current: dict = Depends(get_current_user)):
    import json
    m = json.loads(mapping)
    df, _ = await _read_and_parse(file)
    result = validate_and_normalise(df, m)
    return ValidateOut(
        ok=result["ok"], blocking=result["blocking"], warnings=result["warnings"],
        stats=result["stats"], rejected_preview=result["rejected"][:20],
    )


@router.post("/commit", response_model=ImportOut)
async def commit(file: UploadFile = File(...),
                 mapping: str = Form(...),
                 current: dict = Depends(require_persistent_write)):
    import json
    m = json.loads(mapping)
    content = await file.read()
    df = parse_file(file.filename or "", content)
    fh = file_hash(content)

    db = get_db()
    ent_oid = ObjectId(current["enterprise_id"])

    # Idempotent: reject re-import of exact file
    existing = await db.import_batches.find_one({
        "enterprise_id": ent_oid, "file_hash": fh, "status": "completed",
    })
    if existing:
        raise HTTPException(status_code=409, detail="This file was already imported for your enterprise.")

    result = validate_and_normalise(df, m)
    if not result["ok"]:
        raise HTTPException(status_code=400, detail={"blocking": result["blocking"], "warnings": result["warnings"]})

    batch_doc = {
        "enterprise_id": ent_oid,
        "filename": file.filename,
        "file_hash": fh,
        "mapping_snapshot": m,
        "status": "writing",
        "rows_total": result["stats"]["rows_total"],
        "started_at": datetime.now(timezone.utc),
        "user_id": ObjectId(current["id"]),
        "rejected": result["rejected"][:200],
    }
    batch_id_ins = await db.import_batches.insert_one(batch_doc)
    batch_id = str(batch_id_ins.inserted_id)

    ins = await insert_rows(db, current["enterprise_id"], result["rows"], batch_id)

    # analysis_as_of = latest order_date in enterprise
    latest = await db.transactions.find(
        {"enterprise_id": ent_oid}, {"order_date": 1, "_id": 0},
    ).sort("order_date", -1).limit(1).to_list(1)
    analysis_as_of = latest[0]["order_date"] if latest else datetime.now(timezone.utc)
    if isinstance(analysis_as_of, str):
        analysis_as_of = datetime.fromisoformat(analysis_as_of.replace("Z", "+00:00"))
    # Ensure tz-aware for downstream comparisons.
    if analysis_as_of.tzinfo is None:
        analysis_as_of = analysis_as_of.replace(tzinfo=timezone.utc)

    await db.import_batches.update_one(
        {"_id": batch_id_ins.inserted_id},
        {"$set": {
            "status": "completed", "rows_ok": ins["inserted"], "duplicates": ins["duplicates"],
            "finished_at": datetime.now(timezone.utc), "analysis_as_of": analysis_as_of,
            "warnings": result["warnings"],
        }},
    )

    # Compute opportunities
    tx = await db.transactions.find({"enterprise_id": ent_oid}).to_list(None)
    for t in tx:
        if isinstance(t.get("order_date"), str):
            t["order_date"] = datetime.fromisoformat(t["order_date"].replace("Z", "+00:00"))
        if t["order_date"].tzinfo is None:
            t["order_date"] = t["order_date"].replace(tzinfo=timezone.utc)

    opps = compute(tx, analysis_as_of, thresholds=None, enterprise_id=current["enterprise_id"])
    await db.opportunities.delete_many({"enterprise_id": ent_oid})
    if opps:
        docs = []
        for o in opps:
            docs.append({**o, "enterprise_id": ent_oid, "import_batch_id": batch_id_ins.inserted_id,
                         "created_at": datetime.now(timezone.utc), "status": "OPEN"})
        await db.opportunities.insert_many(docs)

    return ImportOut(
        batch_id=batch_id, inserted=ins["inserted"], duplicates=ins["duplicates"],
        stats=result["stats"], warnings=result["warnings"], analysis_as_of=analysis_as_of,
    )


@router.get("/batches")
async def list_batches(current: dict = Depends(get_current_user)):
    db = get_db()
    docs = await db.import_batches.find({"enterprise_id": ObjectId(current["enterprise_id"])})\
        .sort("started_at", -1).limit(20).to_list(20)
    for d in docs:
        d["id"] = str(d.pop("_id"))
        d["enterprise_id"] = str(d["enterprise_id"])
        if d.get("user_id"): d["user_id"] = str(d["user_id"])
    return docs
