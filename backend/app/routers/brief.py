"""Daily Recovery Brief endpoint — grounded LLM narrative over deterministic facts."""
from __future__ import annotations
from fastapi import APIRouter, Depends, Query

from ..security import get_current_user
from ..services.brief_metrics import build_facts
from ..services.ai_brief import compose


router = APIRouter(prefix="/api/brief", tags=["brief"])


@router.get("/daily")
async def daily_brief(current: dict = Depends(get_current_user),
                      use_llm: bool = Query(True, description="Set false to skip LLM and force deterministic template.")):
    facts = await build_facts(current["enterprise_id"])
    if not use_llm:
        # deterministic fallback path
        from ..services.ai_brief import deterministic_brief
        return deterministic_brief(facts)
    return await compose(facts)
