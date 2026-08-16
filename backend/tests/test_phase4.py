"""Phase 4 acceptance tests: Daily Brief grounding + share tokens security."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import asyncio
import pytest

from app.services.ai_brief import (
    _validate_grounding, deterministic_brief, compose, _inr_short,
)
from app.services.share_tokens import (
    issue_share_token, verify_share_token, revoke_share_token,
    ShareTokenInvalid,
)


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# --------- Deterministic brief structural / grounding tests ---------

def _facts_fixture():
    return {
        "brief_version": "brief-v1.0.0",
        "generated_at": "2026-06-30T00:00:00+00:00",
        "analysis_as_of": "2026-06-30T00:00:00+00:00",
        "summary_counts": {
            "total_opportunities": 418,
            "estimated_recovery_deduped_paise": 56195701,
            "verified_recovery_paise": 62445,
            "verified_recovery_count": 3,
            "overdue_actions": 4,
        },
        "risks_by_type": [
            {"type": "LAPSED", "count": 55, "gross_paise": 40000000},
            {"type": "DECLINING", "count": 33, "gross_paise": 20000000},
        ],
        "top_priorities": [
            {"type": "DECLINING", "outlet_code": "O1", "outlet_name": "Pankaj Provisions",
             "distributor_code": "DIST-06", "salesperson_code": "SP-11",
             "salesperson_name": "Suresh Gupta", "region": "West",
             "est_recovery_paise": 500000, "priority_score": 88, "confidence": 0.7,
             "reason": "-30%", "recommended_action": "Call SP"},
        ],
        "salesperson_workload": [
            {"salesperson_code": "SP-11", "open_actions": 6, "open_est_paise": 1_20_000},
        ],
    }


def test_deterministic_brief_shape():
    b = deterministic_brief(_facts_fixture())
    assert b["narrative_source"] == "deterministic"
    for lang in ("en", "hi"):
        assert set(b[lang].keys()) == {
            "date_line", "management_summary", "top_priorities",
            "risks", "salesperson_workload",
        }
    # Hindi block must contain at least one Devanagari character (0900-097F)
    hi_blob = " ".join(str(v) for v in b["hi"].values())
    assert any('\u0900' <= ch <= '\u097F' for ch in hi_blob), "Hindi block has no Devanagari"


def test_deterministic_brief_never_invents_money():
    facts = _facts_fixture()
    b = deterministic_brief(facts)
    # Grounding must pass on our own deterministic output.
    assert _validate_grounding({"en": b["en"], "hi": b["hi"]}, facts)


def test_grounding_rejects_invented_money_values():
    facts = _facts_fixture()
    bad = {
        "en": {
            "date_line": "Data through 2026-06-30",
            "management_summary": "Estimated ₹999.99 Cr recovery is available.",
            "top_priorities": [],
            "risks": "",
            "salesperson_workload": [],
        },
        "hi": {"date_line": "", "management_summary": "", "top_priorities": [],
               "risks": "", "salesperson_workload": []},
    }
    assert not _validate_grounding(bad, facts)


def test_compose_falls_back_when_llm_unavailable():
    facts = _facts_fixture()

    async def raise_caller(_):
        raise RuntimeError("EMERGENT_LLM_KEY not configured")

    out = asyncio.get_event_loop().run_until_complete(
        compose(facts, _llm_caller=raise_caller)
    )
    assert out["narrative_source"] == "deterministic"


def test_compose_uses_llm_when_grounded():
    facts = _facts_fixture()
    est = _inr_short(facts["summary_counts"]["estimated_recovery_deduped_paise"])
    ver = _inr_short(facts["summary_counts"]["verified_recovery_paise"])

    async def good_caller(_):
        return {
            "en": {
                "date_line": "Data through 2026-06-30",
                "management_summary": f"Total {est} estimated; {ver} verified so far.",
                "top_priorities": ["1. Pankaj Provisions"],
                "risks": "Contained.",
                "salesperson_workload": ["SP-11: 6 open"],
            },
            "hi": {
                "date_line": "30 जून 2026 तक",
                "management_summary": f"कुल अनुमान {est}; {ver} verified।",
                "top_priorities": ["1. Pankaj Provisions"],
                "risks": "Contained.",
                "salesperson_workload": ["SP-11: 6 open"],
            },
        }

    out = asyncio.get_event_loop().run_until_complete(
        compose(facts, _llm_caller=good_caller)
    )
    assert out["narrative_source"] == "gpt-5.2"
    assert out["en"]["management_summary"].startswith("Total ")


def test_compose_falls_back_on_invented_llm_money():
    facts = _facts_fixture()

    async def bad_caller(_):
        return {
            "en": {"date_line": "", "management_summary": "Recovered ₹9,999 Cr magic",
                   "top_priorities": [], "risks": "", "salesperson_workload": []},
            "hi": {"date_line": "", "management_summary": "",
                   "top_priorities": [], "risks": "", "salesperson_workload": []},
        }

    out = asyncio.get_event_loop().run_until_complete(
        compose(facts, _llm_caller=bad_caller)
    )
    assert out["narrative_source"] == "deterministic_fallback_grounding_failed"


# --------- Share token signing / verify / revoke -------------------------

def test_share_token_issue_and_verify_roundtrip():
    tok = issue_share_token(recovery_id="6a5a1234567890abcdef1234",
                            enterprise_id="6a5a16be0ca3cf9a1ffea7bb",
                            issued_by="tester")
    payload = _run(verify_share_token(tok["token"]))
    assert payload["typ"] == "proof"
    assert payload["rid"] == "6a5a1234567890abcdef1234"
    assert payload["ent"] == "6a5a16be0ca3cf9a1ffea7bb"
    assert payload["jti"] == tok["jti"]


def test_share_token_rejects_tampered_signature():
    tok = issue_share_token(recovery_id="6a5a1234567890abcdef1234",
                            enterprise_id="6a5a16be0ca3cf9a1ffea7bb",
                            issued_by="tester")
    # Flip the last non-'=' character in the signature
    bad = tok["token"][:-2] + ("A" if tok["token"][-2] != "A" else "B") + tok["token"][-1]
    with pytest.raises(ShareTokenInvalid):
        _run(verify_share_token(bad))


def test_share_token_rejects_expired():
    import jwt as pyjwt
    import os
    payload = {
        "typ": "proof", "jti": "x", "rid": "r", "ent": "e",
        "exp": datetime.now(timezone.utc) - timedelta(seconds=5),
        "iat": datetime.now(timezone.utc) - timedelta(seconds=10),
    }
    tok = pyjwt.encode(payload, os.environ["JWT_SECRET"], algorithm="HS256")
    with pytest.raises(ShareTokenInvalid) as ei:
        _run(verify_share_token(tok))
    assert "expired" in str(ei.value)


def test_share_token_rejects_wrong_type():
    """An access token should never be usable as a proof token."""
    from app.security import create_access_token
    tok = create_access_token("u", "e@x.com", "DEMO", "e", is_demo=True)
    with pytest.raises(ShareTokenInvalid) as ei:
        _run(verify_share_token(tok))
    assert "wrong_token_type" in str(ei.value)


def test_share_token_revocation():
    tok = issue_share_token(recovery_id="6a5a1234567890abcdef1234",
                            enterprise_id="6a5a16be0ca3cf9a1ffea7bb",
                            issued_by="tester")
    # Verify works pre-revocation
    _run(verify_share_token(tok["token"]))
    # Revoke by jti
    _run(revoke_share_token(tok["jti"], revoked_by="tester"))
    with pytest.raises(ShareTokenInvalid) as ei:
        _run(verify_share_token(tok["token"]))
    assert "revoked" in str(ei.value)
