"""Regression tests for the Phase 2 corrections."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import pytest
from app.services.recovery_engine import compute, dedupe_topline

AS_OF = datetime(2026, 6, 30, tzinfo=timezone.utc)


def _tx(dist, outlet, sku, days_ago, paise, invoice=None):
    return {
        "distributor_code": dist, "outlet_code": outlet, "outlet_name": outlet,
        "salesperson_code": "SP1", "salesperson_name": "SP1",
        "beat_or_route": "B1", "region": "West", "sku_code": sku,
        "invoice_no": invoice or f"I-{outlet}-{days_ago}",
        "order_date": AS_OF - timedelta(days=days_ago),
        "net_sales_paise": paise, "quantity": 1,
    }


def test_lapsed_sparse_history_estimates_from_positive_months_only():
    """Regression: an outlet with 3 invoices spread across only 2 calendar months
    in the prior 90-120d window must NOT get est_recovery = 0. Median must be
    computed from POSITIVE monthly totals only (zero-activity months excluded)."""
    tx = [
        _tx("D1", "SHREE", "S1", 100, 4_00_000),   # ~day 100 (month t-3/t-4)
        _tx("D1", "SHREE", "S1", 80, 3_00_000),    # ~day 80  (month t-3)
        _tx("D1", "SHREE", "S1", 60, 2_50_000),    # ~day 60  (month t-2/t-3)
    ]
    # Peers to keep whitespace/other calcs quiet
    for outlet in ["P1", "P2", "P3"]:
        for d in [70, 45, 20]:
            tx.append(_tx("D1", outlet, "S1", d, 3_00_000))

    opps = compute(tx, AS_OF)
    lapsed = [o for o in opps if o["type"] == "LAPSED" and o["outlet_code"] == "SHREE"]
    assert len(lapsed) == 1
    o = lapsed[0]
    assert o["est_recovery_paise"] > 0, (
        f"Expected positive est_recovery for sparse-history lapsed outlet, "
        f"got {o['est_recovery_paise']}. inputs: {o['inputs_snapshot']}"
    )
    snap = o["inputs_snapshot"]
    assert "positive_monthly_totals" in snap
    assert "active_month_count" in snap
    assert snap["active_month_count"] >= 1
    assert all(v > 0 for v in snap["positive_monthly_totals"])
    # Median of positive months for these three invoices ≈ ~3L; assert bounded.
    assert 1_00_000 <= o["est_recovery_paise"] <= 5_00_000


def test_topline_still_reconciles_with_precedence_after_fix():
    """After the estimator fix, dedupe_topline must still apply the
    LAPSED > DECLINING > MISSED > WHITESPACE precedence per outlet."""
    tx = []
    # OD1 triggers LAPSED (sparse) — three invoices in prior 90d only
    for d, p in [(100, 4_00_000), (80, 3_00_000), (60, 2_50_000)]:
        tx.append(_tx("D1", "OD1", "S1", d, p))
    # Peers so whitespace can also trigger on OD1
    for outlet in ["P1", "P2", "P3"]:
        for d in [70, 45, 20]:
            tx.append(_tx("D1", outlet, "S1", d, 3_00_000))
    # OD2 triggers DECLINING (baseline > 0, drop >= 25%)
    tx.append(_tx("D1", "OD2", "S1", 45, 4_00_000, invoice="OD2-P"))
    tx.append(_tx("D1", "OD2", "S1", 15, 2_00_000, invoice="OD2-N"))

    opps = compute(tx, AS_OF)
    per_outlet = {}
    for o in opps:
        per_outlet.setdefault(o["outlet_code"], []).append(o)
    # OD1 has at least LAPSED
    assert any(o["type"] == "LAPSED" for o in per_outlet.get("OD1", []))
    # OD2 has DECLINING
    assert any(o["type"] == "DECLINING" for o in per_outlet.get("OD2", []))

    topline = dedupe_topline(opps)
    lapsed_od1 = next(o for o in per_outlet["OD1"] if o["type"] == "LAPSED")
    declining_od2 = next(o for o in per_outlet["OD2"] if o["type"] == "DECLINING")
    expected = lapsed_od1["est_recovery_paise"] + declining_od2["est_recovery_paise"]
    assert topline == expected, f"Top-line mismatch: {topline} vs expected {expected}"
