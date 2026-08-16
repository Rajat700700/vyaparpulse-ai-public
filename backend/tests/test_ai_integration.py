"""Integration RED/GREEN tests for the /api/imports/preview AI wiring."""
import io
import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import pytest
from fastapi.testclient import TestClient
import importlib

UNKNOWN_CSV = (
    "Channel Partner Key,Channel Partner Name,Field Officer ID,Field Officer,"
    "Territory Loop,Customer Ledger Code,Customer Trade Name,Posting Day,"
    "Billing Document,Material Ledger,Material Description,Primary Units,"
    "Taxable Value,Sales Zone\n"
    "DQA,QA Distributor,FO-17,Asha Singh,ROUTE-9,OUT-QA-1,QA Kirana,2026-06-15,"
    "INV-QA-001,MAT-QA-01,QA Product,12,4800,North\n"
)


def _client():
    server = importlib.import_module("server")
    return TestClient(server.app)


def _login(c):
    r = c.post("/api/auth/login", json={
        "email": os.environ["ADMIN_EMAIL"],
        "password": os.environ["ADMIN_PASSWORD"],
    })
    assert r.status_code == 200
    return r.json()["access_token"]


def test_territory_loop_must_not_score_region_at_high_rules_confidence():
    """Regression: partial-word overlap should NOT trump AI. 'Territory Loop'
    must stay below 0.85 for the rules mapper so AI can weigh in."""
    from app.services.mapping import suggest_mapping
    m = suggest_mapping(["Territory Loop"])
    assigned = m.get("Territory Loop")
    if assigned is not None:
        assert assigned["confidence"] < 0.85, (
            f"partial-word overlap should not reach rules-first threshold: {assigned}"
        )


def test_exact_alias_still_matches_rules_at_high_confidence():
    """Do not regress the deterministic path: exact aliases still map ≥ 0.85."""
    from app.services.mapping import suggest_mapping
    m = suggest_mapping(["Distributor Code", "Order Date", "Invoice Number", "Region"])
    for header in ("Distributor Code", "Order Date", "Invoice Number", "Region"):
        assert header in m, f"{header} should be mapped by rules"
        assert m[header]["confidence"] >= 0.85, f"{header} regressed: {m[header]}"


def test_preview_endpoint_returns_ai_source_for_unknown_headers():
    """Route-level integration: unfamiliar headers must come back with
    source='ai' when the AI provider is available."""
    from app.services import ai_mapping

    async def fake_ai(headers):
        # Emulate a good AI response covering the required fields the CSV has
        return {
            "Channel Partner Key": {"canonical_field": "distributor_code", "confidence": 0.9,
                                    "reason": "channel partner is distributor"},
            "Field Officer ID": {"canonical_field": "salesperson_code", "confidence": 0.88,
                                 "reason": "field officer maps to salesperson"},
            "Territory Loop": {"canonical_field": "beat_or_route", "confidence": 0.82,
                               "reason": "route/beat"},
            "Customer Ledger Code": {"canonical_field": "outlet_code", "confidence": 0.9,
                                     "reason": "customer code"},
            "Customer Trade Name": {"canonical_field": "outlet_name", "confidence": 0.9,
                                    "reason": "trade name"},
            "Posting Day": {"canonical_field": "order_date", "confidence": 0.85,
                            "reason": "posting date"},
            "Billing Document": {"canonical_field": "invoice_no", "confidence": 0.85,
                                 "reason": "invoice/billing doc"},
            "Material Ledger": {"canonical_field": "sku_code", "confidence": 0.85,
                                "reason": "material code"},
            "Material Description": {"canonical_field": "sku_name", "confidence": 0.9,
                                     "reason": "material description"},
            "Primary Units": {"canonical_field": "quantity", "confidence": 0.8,
                              "reason": "unit count"},
            "Taxable Value": {"canonical_field": "net_sales", "confidence": 0.7,
                              "reason": "taxable = net"},
        }
    ai_mapping.set_llm_caller(fake_ai)
    try:
        with _client() as c:
            token = _login(c)
            r = c.post(
                "/api/imports/preview",
                headers={"Authorization": f"Bearer {token}"},
                files={"file": ("qa_unknown_headers.csv", UNKNOWN_CSV.encode(), "text/csv")},
            )
            assert r.status_code == 200, r.text
            body = r.json()
    finally:
        ai_mapping.set_llm_caller(None)

    m = body["mapping_suggestion"]

    # AI-source assertions
    assert m.get("Channel Partner Key", {}).get("source") == "ai"
    assert m["Channel Partner Key"]["target"] == "distributor_code"
    assert m["Channel Partner Key"]["confidence"] >= 0.5
    assert "reason" in m["Channel Partner Key"]

    assert m.get("Field Officer ID", {}).get("source") == "ai"
    assert m["Field Officer ID"]["target"] == "salesperson_code"

    # Territory Loop must NOT be rules-mapped at high confidence for region
    tl = m.get("Territory Loop")
    if tl:
        assert not (tl.get("source") == "rules" and tl.get("target") == "region"), tl

    # AI status must be visible for the UI
    assert body.get("ai_status") == "ok"


def test_preview_returns_ai_unavailable_when_provider_fails():
    from app.services import ai_mapping

    async def broken_ai(headers):
        raise RuntimeError("provider down")

    ai_mapping.set_llm_caller(broken_ai)
    try:
        with _client() as c:
            token = _login(c)
            r = c.post(
                "/api/imports/preview",
                headers={"Authorization": f"Bearer {token}"},
                files={"file": ("qa_unknown_headers.csv", UNKNOWN_CSV.encode(), "text/csv")},
            )
            assert r.status_code == 200, r.text
            body = r.json()
    finally:
        ai_mapping.set_llm_caller(None)

    # Contract with the frontend: ai_status distinguishes "silent no-op" from
    # "actually broken", so the UI can display "AI unavailable — review manually".
    assert body["ai_status"] == "unavailable"


def test_ai_never_overrides_high_confidence_rules_match():
    """If rules give a header ≥0.85, AI must not overwrite it."""
    from app.services import ai_mapping

    async def aggressive_ai(headers):
        return {h: {"canonical_field": "region", "confidence": 0.99, "reason": "x"} for h in headers}

    ai_mapping.set_llm_caller(aggressive_ai)
    try:
        with _client() as c:
            token = _login(c)
            csv = "Distributor Code,Region\nD1,North\n"
            r = c.post(
                "/api/imports/preview",
                headers={"Authorization": f"Bearer {token}"},
                files={"file": ("f.csv", csv.encode(), "text/csv")},
            )
            body = r.json()
    finally:
        ai_mapping.set_llm_caller(None)

    m = body["mapping_suggestion"]
    assert m["Distributor Code"]["source"] == "rules"
    assert m["Distributor Code"]["target"] == "distributor_code"
    assert m["Region"]["source"] == "rules"
    assert m["Region"]["target"] == "region"
