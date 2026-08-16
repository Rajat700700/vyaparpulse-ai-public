"""Action state machine.

States: ASSIGNED -> IN_PROGRESS -> (COMPLETED | SKIPPED)
Direct edges also allowed:
  ASSIGNED --skip(reason)--> SKIPPED
  ASSIGNED --complete(invoice_ref, claimed)--> COMPLETED

Terminal: COMPLETED, SKIPPED. No further transitions.
"""
from __future__ import annotations
from datetime import datetime, timezone


class InvalidTransition(Exception):
    pass


class RequiresSkipReason(Exception):
    pass


ACTION_TRANSITIONS = {
    ("ASSIGNED", "start"): "IN_PROGRESS",
    ("ASSIGNED", "skip"): "SKIPPED",
    ("IN_PROGRESS", "complete"): "COMPLETED",
    ("IN_PROGRESS", "skip"): "SKIPPED",
}


def transition_action(action: dict, event: str, *, by: str,
                      invoice_ref: str | None = None,
                      claimed_paise: int | None = None,
                      skip_reason: str | None = None,
                      notes: str | None = None) -> dict:
    """Return a new action dict with the transition applied."""
    now = datetime.now(timezone.utc)
    current = action.get("status")
    key = (current, event)
    if key not in ACTION_TRANSITIONS:
        raise InvalidTransition(f"Cannot {event} from {current}")
    new_status = ACTION_TRANSITIONS[key]

    updated = dict(action)
    updated["status"] = new_status

    if event == "start":
        updated.setdefault("started_at", now)
    if event == "complete":
        updated["completed_at"] = now
        updated["completed_by"] = by
        if invoice_ref:
            updated["invoice_ref"] = invoice_ref
        if claimed_paise is not None:
            updated["claimed_paise"] = int(claimed_paise)
    if event == "skip":
        if not skip_reason:
            raise RequiresSkipReason("skip_reason is required to skip an action")
        updated["completed_at"] = now
        updated["skip_reason"] = skip_reason
    if notes:
        updated["notes"] = notes
    return updated
