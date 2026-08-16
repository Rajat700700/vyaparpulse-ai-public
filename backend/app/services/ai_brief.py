"""AI Daily Recovery Brief writer.

The LLM (GPT-5.2 via Emergent Universal Key) receives structured deterministic
facts and returns a JSON brief with narrative sections in English and
Hindi/Hinglish. Every ₹ and count in the LLM output must be echoed VERBATIM
from the facts — the calling router validates this and rewrites to a
deterministic template if the LLM tries to invent numbers or is unavailable.
"""
from __future__ import annotations
import asyncio
import json
import os
import re
from typing import Any, Callable


# --- Deterministic fallback template (used when LLM unavailable or invents) ---

def _inr_short(paise: int) -> str:
    r = paise / 100
    if r >= 10_000_000:
        return f"₹{r / 10_000_000:.2f} Cr"
    if r >= 100_000:
        return f"₹{r / 100_000:.2f} L"
    if r >= 1_000:
        return f"₹{r / 1_000:.1f} K"
    # Preserve paise precision for small amounts (e.g. ₹624.45)
    return f"₹{r:,.2f}"


def deterministic_brief(facts: dict) -> dict[str, Any]:
    """Compose the brief entirely from facts — no LLM, no arithmetic."""
    c = facts["summary_counts"]
    top = facts["top_priorities"]
    risks = facts["risks_by_type"]
    sp = facts["salesperson_workload"]

    date_iso = (facts.get("analysis_as_of") or "").split("T")[0] or "today"

    en_summary = (
        f"Data through {date_iso}. {c['total_opportunities']} open opportunities "
        f"worth {_inr_short(c['estimated_recovery_deduped_paise'])} deduped. "
        f"{c['verified_recovery_count']} recoveries verified "
        f"({_inr_short(c['verified_recovery_paise'])}). "
        f"{c['overdue_actions']} overdue actions need attention today."
    )
    hi_summary = (
        f"{date_iso} तक का डेटा। {c['total_opportunities']} ओपन अवसर, "
        f"deduped अनुमान {_inr_short(c['estimated_recovery_deduped_paise'])}। "
        f"अब तक verify हुई recovery: {c['verified_recovery_count']} "
        f"({_inr_short(c['verified_recovery_paise'])})। "
        f"आज {c['overdue_actions']} overdue actions पर ध्यान दें।"
    )

    priority_lines_en = [
        f"{i+1}. {p['type']} · {p['outlet_name']} ({p['distributor_code']}) — "
        f"{_inr_short(p['est_recovery_paise'])} · score {p['priority_score']} · "
        f"SP {p['salesperson_code']} · {p['recommended_action']}"
        for i, p in enumerate(top)
    ]
    priority_lines_hi = [
        f"{i+1}. {p['type']} · {p['outlet_name']} ({p['distributor_code']}) — "
        f"{_inr_short(p['est_recovery_paise'])} · स्कोर {p['priority_score']} · "
        f"SP {p['salesperson_code']}"
        for i, p in enumerate(top)
    ]

    risk_line_en = ", ".join(
        f"{r['type']} ({r['count']} outlets, gross {_inr_short(r['gross_paise'])})"
        for r in risks
    ) or "No risks flagged."
    risk_line_hi = ", ".join(
        f"{r['type']} ({r['count']} outlets, gross {_inr_short(r['gross_paise'])})"
        for r in risks
    ) or "कोई risk नहीं।"

    sp_lines_en = [
        f"{s['salesperson_code']}: {s['open_actions']} open actions worth "
        f"{_inr_short(s['open_est_paise'])}"
        for s in sp
    ]
    sp_lines_hi = [
        f"{s['salesperson_code']}: {s['open_actions']} खुले actions "
        f"({_inr_short(s['open_est_paise'])})"
        for s in sp
    ]

    return {
        "brief_version": facts["brief_version"],
        "generated_at": facts["generated_at"],
        "analysis_as_of": facts.get("analysis_as_of"),
        "narrative_source": "deterministic",
        "en": {
            "date_line": f"Data through {date_iso}",
            "management_summary": en_summary,
            "top_priorities": priority_lines_en,
            "risks": risk_line_en,
            "salesperson_workload": sp_lines_en,
        },
        "hi": {
            "date_line": f"{date_iso} तक का डेटा",
            "management_summary": hi_summary,
            "top_priorities": priority_lines_hi,
            "risks": risk_line_hi,
            "salesperson_workload": sp_lines_hi,
        },
        "facts": facts,
    }


# --- LLM caller (GPT-5.2 via Emergent Universal Key) --------------------

# ₹-containing tokens as they appear in the deterministic-derived strings.
_MONEY_TOKEN_RE = re.compile(r"₹\s*[\d,]+(?:\.\d+)?\s*(?:Cr|L|K)?", re.IGNORECASE)


def _allowed_tokens(facts: dict) -> set[str]:
    """Extract every ₹ token that the LLM is permitted to emit."""
    tokens: set[str] = set()
    for p in facts["top_priorities"]:
        tokens.add(_inr_short(int(p["est_recovery_paise"])))
    for r in facts["risks_by_type"]:
        tokens.add(_inr_short(int(r["gross_paise"])))
    for s in facts["salesperson_workload"]:
        tokens.add(_inr_short(int(s["open_est_paise"])))
    c = facts["summary_counts"]
    tokens.add(_inr_short(int(c["estimated_recovery_deduped_paise"])))
    tokens.add(_inr_short(int(c["verified_recovery_paise"])))
    return tokens


def _validate_grounding(narrative: dict, facts: dict) -> bool:
    """Return True iff every ₹ token found in the narrative is a permitted
    fact-derived token. Any invented ₹ value fails grounding."""
    allowed = _allowed_tokens(facts)
    for lang in ("en", "hi"):
        block = narrative.get(lang) or {}
        blob = " ".join(str(v) for v in _flatten(block))
        for m in _MONEY_TOKEN_RE.findall(blob):
            token = m.strip().replace(" ", "")
            # normalise both sides by stripping spaces so "₹5.62 L" == "₹5.62L"
            if not any(token == a.replace(" ", "") for a in allowed):
                return False
    return True


def _flatten(x):
    if isinstance(x, dict):
        for v in x.values():
            yield from _flatten(v)
    elif isinstance(x, list):
        for v in x:
            yield from _flatten(v)
    else:
        yield x


async def _live_llm_call(facts: dict) -> dict:
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        raise RuntimeError("EMERGENT_LLM_KEY not configured")
    from emergentintegrations.llm.chat import LlmChat, UserMessage

    # Build a display-only facts payload — every ₹ pre-formatted. The LLM MUST
    # copy these display strings verbatim; the raw *_paise integers are
    # deliberately withheld so the LLM has nothing to do arithmetic on.
    display = {
        "date": (facts.get("analysis_as_of") or "").split("T")[0],
        "summary": {
            "total_opportunities": facts["summary_counts"]["total_opportunities"],
            "estimated_recovery_deduped": _inr_short(facts["summary_counts"]["estimated_recovery_deduped_paise"]),
            "verified_recovery": _inr_short(facts["summary_counts"]["verified_recovery_paise"]),
            "verified_recovery_count": facts["summary_counts"]["verified_recovery_count"],
            "overdue_actions": facts["summary_counts"]["overdue_actions"],
        },
        "risks_by_type": [
            {"type": r["type"], "count": r["count"],
             "gross_display": _inr_short(r["gross_paise"])}
            for r in facts["risks_by_type"]
        ],
        "top_priorities": [
            {"rank": i + 1, "type": p["type"], "outlet_name": p["outlet_name"],
             "outlet_code": p["outlet_code"], "distributor_code": p["distributor_code"],
             "salesperson_code": p["salesperson_code"],
             "priority_score": p["priority_score"],
             "est_recovery_display": _inr_short(p["est_recovery_paise"]),
             "recommended_action": p["recommended_action"]}
            for i, p in enumerate(facts["top_priorities"])
        ],
        "salesperson_workload": [
            {"salesperson_code": s["salesperson_code"],
             "open_actions": s["open_actions"],
             "open_est_display": _inr_short(s["open_est_paise"])}
            for s in facts["salesperson_workload"]
        ],
    }

    system = (
        "You are an Indian FMCG revenue-recovery analyst writing a concise DAILY "
        "BRIEF for enterprise leadership. You will receive a JSON `display` payload "
        "containing PRE-FORMATTED strings for every ₹ value. Follow these rules "
        "strictly:\n"
        "1. NEVER perform arithmetic. NEVER convert, scale, round or invent ₹ values.\n"
        "2. Every ₹ value in your output MUST be copied VERBATIM from a `*_display` "
        "field in the payload (e.g. ₹5.62 L, ₹624.45, ₹11.1 K, ₹2.32 L). Do not "
        "modify these strings in any way.\n"
        "3. Return valid JSON of exactly this shape:\n"
        '{"en": {"date_line": str, "management_summary": str, '
        '"top_priorities": [str, ...], "risks": str, "salesperson_workload": [str, ...]}, '
        '"hi": {same keys with Hindi/Hinglish text — Devanagari plus common English '
        'retail vocabulary is fine and field-friendly}}\n'
        "4. Keep the management summary to 2-3 sentences. Priorities in the SAME "
        "order as display.top_priorities. Never translate outlet names, SKU codes "
        "or salesperson codes.\n"
        "5. Do NOT wrap the JSON in code fences."
    )
    prompt = "display payload:\n" + json.dumps(display, ensure_ascii=False)
    chat = (
        LlmChat(api_key=api_key, session_id="daily-brief",
                system_message=system)
        .with_model("openai", "gpt-5.2")
    )
    resp = await chat.send_message(UserMessage(text=prompt))
    text = str(resp).strip()
    if text.startswith("```"):
        text = text.split("```", 2)[-1]
        if text.lstrip().lower().startswith("json"):
            text = text.lstrip()[4:]
        text = text.rsplit("```", 1)[0].strip()
    return json.loads(text)


async def compose(facts: dict, *, timeout: float = 25.0,
                  _llm_caller: Callable | None = None) -> dict:
    """Compose the brief. Try LLM first; on any failure, or if grounding fails,
    fall back to the deterministic template."""
    caller = _llm_caller or _live_llm_call
    try:
        raw = await asyncio.wait_for(caller(facts), timeout=timeout)
    except Exception:
        return deterministic_brief(facts)

    # Shape check
    if (not isinstance(raw, dict)
            or not isinstance(raw.get("en"), dict)
            or not isinstance(raw.get("hi"), dict)):
        return deterministic_brief(facts)

    # Grounding check
    if not _validate_grounding(raw, facts):
        det = deterministic_brief(facts)
        det["narrative_source"] = "deterministic_fallback_grounding_failed"
        return det

    return {
        "brief_version": facts["brief_version"],
        "generated_at": facts["generated_at"],
        "analysis_as_of": facts.get("analysis_as_of"),
        "narrative_source": "gpt-5.2",
        "en": raw["en"],
        "hi": raw["hi"],
        "facts": facts,
    }
