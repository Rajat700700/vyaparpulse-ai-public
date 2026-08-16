"""Deterministic recovery attribution.

Rules (per user directive):
- Invoice `order_date` must satisfy: assigned_at <= order_date <= completed_at + 14d
  (both bounds inclusive; +15d excluded).
- Match on (enterprise_id, distributor_code, outlet_code, invoice_no).
- verified_paise = min(claimed_paise, invoice.net_sales_paise), non-negative.
- Uniqueness at the collection level is enforced by `recovery_key`.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class AttributionResult:
    status: str            # "VERIFIED" | "NO_EVIDENCE"
    verified_paise: int
    invoice_net_paise: int
    invoice_order_date: datetime | None


def recovery_key(enterprise_id: str, distributor_code: str,
                 outlet_code: str, invoice_no: str) -> tuple:
    return (str(enterprise_id), distributor_code, outlet_code, invoice_no)


def verify_recovery(*, invoices: list[dict], invoice_no: str,
                    enterprise_id: str, distributor_code: str, outlet_code: str,
                    assigned_at: datetime, completed_at: datetime,
                    claimed_paise: int) -> AttributionResult:
    if completed_at < assigned_at:
        completed_at = assigned_at
    window_end = completed_at + timedelta(days=14)
    for t in invoices:
        if str(t.get("enterprise_id")) != str(enterprise_id):
            continue
        if t.get("distributor_code") != distributor_code:
            continue
        if t.get("outlet_code") != outlet_code:
            continue
        if t.get("invoice_no") != invoice_no:
            continue
        order_date = t.get("order_date")
        if not isinstance(order_date, datetime):
            continue
        if order_date < assigned_at or order_date > window_end:
            continue
        net = int(t.get("net_sales_paise") or 0)
        verified = max(0, min(int(claimed_paise), net))
        return AttributionResult(
            status="VERIFIED", verified_paise=verified,
            invoice_net_paise=net, invoice_order_date=order_date,
        )
    return AttributionResult(
        status="NO_EVIDENCE", verified_paise=0, invoice_net_paise=0,
        invoice_order_date=None,
    )
