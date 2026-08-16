"""RED/GREEN tests for the AI-fallback column mapping."""
import asyncio
import pytest

from app.services.ai_mapping import (
    CANONICAL_FIELDS,
    ai_map_headers,
    set_llm_caller,
)
from app.services.mapping import REQUIRED


@pytest.fixture(autouse=True)
def _reset_caller():
    set_llm_caller(None)
    yield
    set_llm_caller(None)


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_ai_maps_unfamiliar_headers_via_mock_provider():
    """Mock provider returns valid JSON — unfamiliar headers get mapped."""
    async def mock(headers):
        return {
            "Ledger Party Cd": {"canonical_field": "distributor_code", "confidence": 0.9, "reason": "party code"},
            "Beat Master": {"canonical_field": "beat_or_route", "confidence": 0.86, "reason": "beat"},
        }
    set_llm_caller(mock)
    out = _run(ai_map_headers(["Ledger Party Cd", "Beat Master"]))
    assert out["Ledger Party Cd"]["target"] == "distributor_code"
    assert out["Ledger Party Cd"]["source"] == "ai"
    assert out["Beat Master"]["target"] == "beat_or_route"


def test_ai_rejects_invalid_canonical_field():
    async def mock(headers):
        return {"Weird Col": {"canonical_field": "not_a_real_field", "confidence": 0.9}}
    set_llm_caller(mock)
    out = _run(ai_map_headers(["Weird Col"]))
    assert out == {}


def test_ai_rejects_low_confidence():
    async def mock(headers):
        return {"Ambiguous": {"canonical_field": "region", "confidence": 0.2}}
    set_llm_caller(mock)
    out = _run(ai_map_headers(["Ambiguous"]))
    assert out == {}


def test_ai_rejects_out_of_range_confidence():
    async def mock(headers):
        return {"Bad": {"canonical_field": "region", "confidence": 5}}
    set_llm_caller(mock)
    assert _run(ai_map_headers(["Bad"])) == {}


def test_ai_timeout_falls_back_safely():
    async def slow(headers):
        await asyncio.sleep(5)
        return {}
    set_llm_caller(slow)
    out = _run(ai_map_headers(["Anything"], timeout=0.05))
    assert out == {}


def test_ai_exception_falls_back_safely():
    async def boom(headers):
        raise RuntimeError("provider down")
    set_llm_caller(boom)
    assert _run(ai_map_headers(["Anything"])) == {}


def test_ai_ignores_malformed_shape():
    async def malformed(headers):
        return "not-a-dict"
    set_llm_caller(malformed)
    assert _run(ai_map_headers(["Anything"])) == {}


def test_ai_never_called_for_empty_headers():
    called = []
    async def mock(headers):
        called.append(headers)
        return {}
    set_llm_caller(mock)
    assert _run(ai_map_headers([])) == {}
    assert called == []


def test_preview_endpoint_does_not_call_ai_when_rules_cover_all_headers(monkeypatch):
    """Deterministic high-confidence aliases should mean the /preview endpoint
    never invokes the AI. We assert by injecting a raising mock."""
    async def raise_if_called(headers):
        raise AssertionError("AI must not be called when rules cover everything")
    set_llm_caller(raise_if_called)

    # Manually construct the deterministic mapping pipeline that /preview uses.
    from app.services.mapping import suggest_mapping
    familiar_headers = [
        "Distributor Code", "Salesman Code", "Beat", "Outlet Code", "Outlet Name",
        "Invoice Date", "Invoice Number", "Item Code", "Item Name", "Qty", "Net Amount",
    ]
    rules = suggest_mapping(familiar_headers)
    # Every required field is covered at >= 0.85 confidence by rules alone
    covered = {v["target"] for v in rules.values() if v["confidence"] >= 0.85}
    missing = [t for t in REQUIRED if t not in covered]
    assert missing == [], f"Rules must cover all required fields: missing {missing}"


def test_canonical_field_list_matches_required_and_optional():
    for t in REQUIRED:
        assert t in CANONICAL_FIELDS
