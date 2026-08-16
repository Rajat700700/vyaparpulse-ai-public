"""AI fallback for uncertain column mappings.

Rules-first mapping (services/mapping.py) runs first. Only headers left unmapped or
with low-confidence (< 0.85) suggestions are forwarded to GPT-5.2 via the Emergent
Universal Key. The AI is given ONLY the header names and the canonical-field
allowlist — never transaction values. Its output is strictly validated:
  - target must be in the canonical allowlist
  - confidence must be a float in [0, 1]
  - low-confidence AI suggestions (< 0.5) are dropped
Any timeout, exception, or malformed response falls back safely to leaving the
column unmapped so the user can map it manually.
"""
from __future__ import annotations
import asyncio
import json
import os
from typing import Awaitable, Callable, Optional

from .mapping import ALIASES

CANONICAL_FIELDS = list(ALIASES.keys())
_LOW_CONF_THRESHOLD = 0.5
_MAX_HEADERS = 40
_DEFAULT_TIMEOUT = 20.0

LLMCaller = Callable[[list[str]], Awaitable[dict]]

# Test/injection hook. When set, replaces the live LLM call.
_llm_caller: Optional[LLMCaller] = None


def set_llm_caller(fn: Optional[LLMCaller]) -> None:
    global _llm_caller
    _llm_caller = fn


def _validate(raw: dict, headers: list[str]) -> dict:
    """Filter LLM output down to well-formed entries mapped to canonical fields."""
    if not isinstance(raw, dict):
        return {}
    out: dict[str, dict] = {}
    for h in headers:
        entry = raw.get(h) if raw.get(h) is not None else raw.get(h.strip())
        if not isinstance(entry, dict):
            continue
        target = entry.get("canonical_field")
        conf = entry.get("confidence")
        reason = entry.get("reason") or ""
        if target is None or target not in CANONICAL_FIELDS:
            continue
        if not isinstance(conf, (int, float)):
            continue
        if not (0.0 <= float(conf) <= 1.0):
            continue
        if float(conf) < _LOW_CONF_THRESHOLD:
            continue
        out[h] = {
            "target": target,
            "confidence": round(float(conf), 2),
            "source": "ai",
            "reason": str(reason)[:200],
        }
    return out


async def ai_map_headers(unmapped_headers: list[str],
                         timeout: float = _DEFAULT_TIMEOUT) -> dict:
    """Backwards-compatible wrapper. Returns only the mapping dict."""
    m, _ = await ai_map_headers_verbose(unmapped_headers, timeout)
    return m


async def ai_map_headers_verbose(unmapped_headers: list[str],
                                 timeout: float = _DEFAULT_TIMEOUT
                                 ) -> tuple[dict, str]:
    """Same as ai_map_headers, but also returns a status string the UI can
    show: ``"skipped"`` (no candidates), ``"ok"`` (call succeeded — even if
    nothing passed validation) or ``"unavailable"`` (timeout / exception /
    missing key). Never raises."""
    if not unmapped_headers:
        return {}, "skipped"
    headers = unmapped_headers[:_MAX_HEADERS]
    caller = _llm_caller or _live_llm_call
    try:
        raw = await asyncio.wait_for(caller(headers), timeout=timeout)
    except Exception:
        return {}, "unavailable"
    return _validate(raw, headers), "ok"


async def _live_llm_call(headers: list[str]) -> dict:
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        raise RuntimeError("EMERGENT_LLM_KEY not configured")
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    canonical = ", ".join(CANONICAL_FIELDS)
    system = (
        "You are a spreadsheet column-header classifier for an Indian FMCG sales "
        "dataset. Map each header to exactly one of these canonical fields, or null "
        "if uncertain. Never invent new canonical fields.\n"
        f"Allowed canonical fields: {canonical}\n"
        "Respond ONLY with a compact JSON object. For every input header the value "
        'must be either null or {"canonical_field": <one of the allowed or null>, '
        '"confidence": <number 0-1>, "reason": <short string>}.'
    )
    prompt = "Headers:\n" + "\n".join(f"- {h}" for h in headers)
    chat = (
        LlmChat(api_key=api_key, session_id="col-map",
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
