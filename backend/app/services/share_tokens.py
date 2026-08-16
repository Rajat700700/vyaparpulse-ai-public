"""Signed, expiring, revocable share tokens for verified-recovery proof cards.

Uses HS256 JWT so the token is stateless AND signed with the platform's
`JWT_SECRET`. Revocation is tracked via a `share_revocations` collection
keyed by JWT `jti` (unique per-issue), so any share can be revoked without
invalidating others. Tokens carry:
    - jti  : unique ObjectId hex, used for revocation lookup
    - typ  : 'proof'  (distinguished from access/refresh tokens)
    - rid  : recovery_id (ObjectId hex)
    - ent  : enterprise_id (ObjectId hex) — for tenant re-verification
    - iat  : issued-at (unix ts)
    - exp  : expiry   (unix ts)

Public verify_share_token returns the payload OR raises ShareTokenInvalid.
"""
from __future__ import annotations
import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from bson import ObjectId

from ..db import get_db
from ..security import JWT_ALGORITHM, decode_token


class ShareTokenInvalid(Exception):
    pass


def _secret() -> str:
    return os.environ["JWT_SECRET"]


def _default_days() -> int:
    return int(os.environ.get("SHARE_TOKEN_DAYS", "30"))


def issue_share_token(*, recovery_id: str, enterprise_id: str,
                      issued_by: str, ttl_days: int | None = None) -> dict:
    """Create a signed proof token. Returns dict with jti, token, expires_at."""
    jti = secrets.token_urlsafe(16)
    exp = datetime.now(timezone.utc) + timedelta(days=ttl_days or _default_days())
    payload = {
        "typ": "proof",
        "jti": jti,
        "rid": str(recovery_id),
        "ent": str(enterprise_id),
        "iat": datetime.now(timezone.utc),
        "exp": exp,
        "iss": issued_by,
    }
    token = jwt.encode(payload, _secret(), algorithm=JWT_ALGORITHM)
    return {"jti": jti, "token": token, "expires_at": exp}


async def verify_share_token(token: str) -> dict:
    """Decode, validate type, and check the revocation list."""
    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        raise ShareTokenInvalid("expired")
    except jwt.InvalidTokenError:
        raise ShareTokenInvalid("invalid_signature")
    if payload.get("typ") != "proof":
        raise ShareTokenInvalid("wrong_token_type")
    jti = payload.get("jti")
    if not jti:
        raise ShareTokenInvalid("missing_jti")
    db = get_db()
    revoked = await db.share_revocations.find_one({"jti": jti})
    if revoked:
        raise ShareTokenInvalid("revoked")
    return payload


async def revoke_share_token(jti: str, *, revoked_by: str) -> bool:
    db = get_db()
    r = await db.share_revocations.update_one(
        {"jti": jti},
        {"$setOnInsert": {
            "jti": jti, "revoked_at": datetime.now(timezone.utc),
            "revoked_by": revoked_by,
        }},
        upsert=True,
    )
    return r.upserted_id is not None or r.modified_count == 0
