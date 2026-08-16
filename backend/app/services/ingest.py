"""Ingestion — parse CSV/XLSX, validate, dedupe, insert."""
import hashlib
import io
from datetime import datetime, timezone
from typing import Any
import pandas as pd
from bson import ObjectId

from .mapping import REQUIRED


def parse_file(filename: str, content: bytes) -> pd.DataFrame:
    lower = filename.lower()
    bio = io.BytesIO(content)
    if lower.endswith(".csv"):
        return pd.read_csv(bio, dtype=str, keep_default_na=False)
    if lower.endswith(".xlsx") or lower.endswith(".xls"):
        return pd.read_excel(bio, dtype=str, keep_default_na=False)
    raise ValueError("Unsupported file type. Please upload CSV or XLSX.")


def file_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _row_hash(distributor_code: str, invoice_no: str, outlet_code: str,
              sku_code: str, order_date: str, quantity: str, net_sales: str,
              source_line: int) -> str:
    key = "|".join([
        distributor_code, invoice_no, outlet_code, sku_code, order_date,
        str(quantity), str(net_sales), str(source_line),
    ])
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _to_date(v: str) -> datetime | None:
    if not v:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y", "%d %b %Y", "%d-%b-%Y"):
        try:
            return datetime.strptime(str(v).strip(), fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    try:
        return pd.to_datetime(v, utc=True, dayfirst=True).to_pydatetime()
    except Exception:
        return None


def _to_float(v: str) -> float | None:
    if v is None or str(v).strip() == "":
        return None
    try:
        return float(str(v).replace(",", "").strip())
    except ValueError:
        return None


def validate_and_normalise(df: pd.DataFrame, mapping: dict[str, str]) -> dict:
    """mapping = {source_header: target_field}. Returns normalised rows + issues."""
    # Reverse mapping check
    covered_targets = set(mapping.values())
    missing = [t for t in REQUIRED if t not in covered_targets]
    if missing:
        return {"ok": False, "blocking": [f"Missing required field mapping: {', '.join(missing)}"],
                "warnings": [], "rows": [], "rejected": [], "stats": {}}

    inv_map = {t: s for s, t in mapping.items()}
    blocking: list[str] = []
    warnings: list[str] = []
    rows: list[dict] = []
    rejected: list[dict] = []
    now = datetime.now(timezone.utc)

    distributors: set[str] = set()
    outlets: set[str] = set()
    skus: set[str] = set()
    min_d = None
    max_d = None
    invoice_outlet: dict[str, set[str]] = {}

    for idx, r in df.iterrows():
        def g(t: str) -> str:
            src = inv_map.get(t)
            return str(r[src]).strip() if src and src in r and r[src] is not None else ""

        errors: list[str] = []
        dist_code = g("distributor_code")
        outlet_code = g("outlet_code")
        sku_code = g("sku_code")
        invoice = g("invoice_no")
        qty = _to_float(g("quantity"))
        net = _to_float(g("net_sales"))
        d = _to_date(g("order_date"))

        for f, val in [("distributor_code", dist_code), ("outlet_code", outlet_code),
                       ("sku_code", sku_code), ("invoice_no", invoice)]:
            if not val:
                errors.append(f"missing {f}")
        if qty is None:
            errors.append("non-numeric quantity")
        if net is None:
            errors.append("non-numeric net_sales")
        if d is None:
            errors.append("invalid date")
        elif d > now:
            errors.append("future date")

        row_flags: list[str] = []
        if net is not None and net < 0:
            row_flags.append("negative_return")

        if errors:
            rejected.append({"row": int(idx) + 2, "errors": errors, "raw": {k: str(v) for k, v in r.items()}})
            continue

        row = {
            "distributor_code": dist_code,
            "salesperson_code": g("salesperson_code"),
            "salesperson_name": g("salesperson_name"),
            "beat_or_route": g("beat_or_route"),
            "outlet_code": outlet_code,
            "outlet_name": g("outlet_name"),
            "order_date": d,
            "invoice_no": invoice,
            "sku_code": sku_code,
            "sku_name": g("sku_name"),
            "quantity": qty,
            "net_sales_paise": int(round(net * 100)),
            "region": g("region"),
            "category": g("category"),
            "brand": g("brand"),
            "gross_paise": int(round((_to_float(g("gross_sales")) or 0) * 100)),
            "discount_paise": int(round((_to_float(g("discount")) or 0) * 100)),
            "return_paise": int(round((_to_float(g("return_value")) or 0) * 100)),
            "flags": row_flags,
            "row_hash": _row_hash(dist_code, invoice, outlet_code, sku_code, d.isoformat(), qty, net, int(idx)),
        }
        rows.append(row)
        distributors.add(dist_code)
        outlets.add(f"{dist_code}|{outlet_code}")
        skus.add(sku_code)
        min_d = d if (min_d is None or d < min_d) else min_d
        max_d = d if (max_d is None or d > max_d) else max_d
        invoice_outlet.setdefault(invoice, set()).add(outlet_code)

    # Warnings
    for inv, outs in invoice_outlet.items():
        if len(outs) > 1:
            warnings.append(f"Invoice {inv} reused across {len(outs)} outlets")

    stats = {
        "rows_total": int(len(df)),
        "rows_ok": len(rows),
        "rows_rejected": len(rejected),
        "distributors": len(distributors),
        "outlets": len(outlets),
        "skus": len(skus),
        "min_date": min_d.isoformat() if min_d else None,
        "max_date": max_d.isoformat() if max_d else None,
    }
    return {"ok": len(rows) > 0, "blocking": blocking, "warnings": warnings,
            "rows": rows, "rejected": rejected, "stats": stats}


async def insert_rows(db, enterprise_id: str, rows: list[dict], batch_id: str) -> dict:
    if not rows:
        return {"inserted": 0, "duplicates": 0}
    ent_oid = ObjectId(enterprise_id)
    batch_oid = ObjectId(batch_id)
    docs = []
    for r in rows:
        docs.append({
            **r,
            "enterprise_id": ent_oid,
            "import_batch_id": batch_oid,
        })
    inserted = 0
    duplicates = 0
    # Bulk upsert-on-conflict via ordered=False on unique (enterprise_id, distributor_code, row_hash)
    from pymongo.errors import BulkWriteError
    try:
        r = await db.transactions.insert_many(docs, ordered=False)
        inserted = len(r.inserted_ids)
    except BulkWriteError as bwe:
        inserted = bwe.details.get("nInserted", 0)
        duplicates = len(bwe.details.get("writeErrors", []))
    return {"inserted": inserted, "duplicates": duplicates}
