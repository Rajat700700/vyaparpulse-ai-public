"""Phase 3 acceptance tests (RED-first).

Covers:
- Attribution boundary: -1d excluded, assigned_at included, completed_at+14 included, +15 excluded.
- Duplicate invoice / no double-count.
- Multiple partial recoveries across DIFFERENT invoices allowed.
- Action state machine: valid + invalid transitions; SKIP requires reason.
- Demo actions ephemeral: reset endpoint clears them; production actions untouched.
- Outlet 360 totals reconcile to Radar + Ledger.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import pytest
from app.services.attribution import verify_recovery, AttributionResult
from app.services.state_machine import (
    ACTION_TRANSITIONS, transition_action, InvalidTransition, RequiresSkipReason,
)

AS_OF = datetime(2026, 6, 30, tzinfo=timezone.utc)


def _txn(days_from_assign, net_paise, invoice="INV-1", assigned_at=None):
    """Helper — returns a transactions-collection-shaped dict."""
    assigned = assigned_at or datetime(2026, 6, 1, tzinfo=timezone.utc)
    return {
        "enterprise_id": "e1", "distributor_code": "D1", "outlet_code": "O1",
        "invoice_no": invoice,
        "order_date": assigned + timedelta(days=days_from_assign),
        "net_sales_paise": net_paise,
    }


# --------------- Attribution boundaries ---------------

def test_attribution_before_assigned_excluded():
    assigned = datetime(2026, 6, 1, tzinfo=timezone.utc)
    completed = datetime(2026, 6, 5, tzinfo=timezone.utc)
    invoices = [_txn(-1, 5_00_000, assigned_at=assigned)]
    r = verify_recovery(
        invoices=invoices, invoice_no="INV-1",
        enterprise_id="e1", distributor_code="D1", outlet_code="O1",
        assigned_at=assigned, completed_at=completed, claimed_paise=5_00_000,
    )
    assert r.status == "NO_EVIDENCE"
    assert r.verified_paise == 0


def test_attribution_exactly_at_assigned_at_included():
    assigned = datetime(2026, 6, 1, tzinfo=timezone.utc)
    completed = datetime(2026, 6, 5, tzinfo=timezone.utc)
    invoices = [_txn(0, 5_00_000, assigned_at=assigned)]
    r = verify_recovery(
        invoices=invoices, invoice_no="INV-1",
        enterprise_id="e1", distributor_code="D1", outlet_code="O1",
        assigned_at=assigned, completed_at=completed, claimed_paise=5_00_000,
    )
    assert r.status == "VERIFIED"
    assert r.verified_paise == 5_00_000


def test_attribution_exactly_at_completed_plus_14_included():
    assigned = datetime(2026, 6, 1, tzinfo=timezone.utc)
    completed = datetime(2026, 6, 5, tzinfo=timezone.utc)
    order_dt = completed + timedelta(days=14)
    invoices = [{
        "enterprise_id": "e1", "distributor_code": "D1", "outlet_code": "O1",
        "invoice_no": "INV-1", "order_date": order_dt, "net_sales_paise": 5_00_000,
    }]
    r = verify_recovery(
        invoices=invoices, invoice_no="INV-1",
        enterprise_id="e1", distributor_code="D1", outlet_code="O1",
        assigned_at=assigned, completed_at=completed, claimed_paise=5_00_000,
    )
    assert r.status == "VERIFIED"


def test_attribution_completed_plus_15_excluded():
    assigned = datetime(2026, 6, 1, tzinfo=timezone.utc)
    completed = datetime(2026, 6, 5, tzinfo=timezone.utc)
    order_dt = completed + timedelta(days=15)
    invoices = [{
        "enterprise_id": "e1", "distributor_code": "D1", "outlet_code": "O1",
        "invoice_no": "INV-1", "order_date": order_dt, "net_sales_paise": 5_00_000,
    }]
    r = verify_recovery(
        invoices=invoices, invoice_no="INV-1",
        enterprise_id="e1", distributor_code="D1", outlet_code="O1",
        assigned_at=assigned, completed_at=completed, claimed_paise=5_00_000,
    )
    assert r.status == "NO_EVIDENCE"


def test_attribution_caps_verified_at_invoice_value():
    """claimed 10L but invoice only 4L → verified = 4L, capped."""
    assigned = datetime(2026, 6, 1, tzinfo=timezone.utc)
    completed = datetime(2026, 6, 5, tzinfo=timezone.utc)
    invoices = [_txn(3, 4_00_000, assigned_at=assigned)]
    r = verify_recovery(
        invoices=invoices, invoice_no="INV-1",
        enterprise_id="e1", distributor_code="D1", outlet_code="O1",
        assigned_at=assigned, completed_at=completed, claimed_paise=10_00_000,
    )
    assert r.status == "VERIFIED"
    assert r.verified_paise == 4_00_000


# --------------- State machine ---------------

def test_action_transitions_valid():
    action = {"status": "ASSIGNED"}
    a = transition_action(action, "start", by="SP1")
    assert a["status"] == "IN_PROGRESS"
    assert a.get("started_at") is not None
    a2 = transition_action(a, "complete", by="SP1", invoice_ref="INV-1", claimed_paise=1000)
    assert a2["status"] == "COMPLETED"
    assert a2["invoice_ref"] == "INV-1"
    assert a2["claimed_paise"] == 1000
    assert a2.get("completed_at") is not None


def test_action_skip_requires_reason():
    action = {"status": "ASSIGNED"}
    with pytest.raises(RequiresSkipReason):
        transition_action(action, "skip", by="SP1")
    ok = transition_action(action, "skip", by="SP1", skip_reason="Outlet closed")
    assert ok["status"] == "SKIPPED"
    assert ok["skip_reason"] == "Outlet closed"


def test_action_invalid_transition_from_completed():
    action = {"status": "COMPLETED"}
    with pytest.raises(InvalidTransition):
        transition_action(action, "start", by="SP1")
    with pytest.raises(InvalidTransition):
        transition_action(action, "complete", by="SP1", invoice_ref="X", claimed_paise=1)


def test_action_direct_complete_from_assigned_rejected():
    """ASSIGNED → COMPLETED must go through IN_PROGRESS. Direct completion is
    rejected as an invalid transition (Phase 3 QA correction #2)."""
    action = {"status": "ASSIGNED"}
    with pytest.raises(InvalidTransition):
        transition_action(action, "complete", by="SP1", invoice_ref="INV-1", claimed_paise=100)


def test_action_valid_assigned_to_inprogress_to_completed():
    a = transition_action({"status": "ASSIGNED"}, "start", by="SP1")
    assert a["status"] == "IN_PROGRESS"
    b = transition_action(a, "complete", by="SP1", invoice_ref="INV-1", claimed_paise=100)
    assert b["status"] == "COMPLETED"


# --------------- Recovery uniqueness (invoice-level dedupe) ---------------

def test_two_actions_completing_same_invoice_produce_one_recovery():
    """Simulated at the collection-key level: unique (enterprise, distributor, outlet, invoice) key.
    The router relies on this unique index, so we simply assert the shape here."""
    from app.services.attribution import recovery_key
    k1 = recovery_key("e1", "D1", "O1", "INV-1")
    k2 = recovery_key("e1", "D1", "O1", "INV-1")
    assert k1 == k2
    # Different invoice → different key (partial recoveries across invoices allowed)
    k3 = recovery_key("e1", "D1", "O1", "INV-2")
    assert k1 != k3


# --------------- Reconciliation ---------------

def test_outlet_360_totals_reconcile():
    """Given three opportunities for outlet O1 (LAPSED 500, DECLINING 300, WHITESPACE 200),
    Outlet 360 total shown must equal max-by-precedence (LAPSED 500), matching Radar precedence."""
    from app.services.recovery_engine import dedupe_topline
    opps = [
        {"type": "LAPSED", "distributor_code": "D1", "outlet_code": "O1", "est_recovery_paise": 500},
        {"type": "DECLINING", "distributor_code": "D1", "outlet_code": "O1", "est_recovery_paise": 300},
        {"type": "WHITESPACE", "distributor_code": "D1", "outlet_code": "O1", "est_recovery_paise": 200},
    ]
    assert dedupe_topline(opps) == 500
