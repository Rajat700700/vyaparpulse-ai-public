"""MongoDB connection and index setup."""
import os
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    return _client


def get_db() -> AsyncIOMotorDatabase:
    global _db
    if _db is None:
        _db = get_client()[os.environ["DB_NAME"]]
    return _db


async def close_client() -> None:
    global _client, _db
    if _client is not None:
        _client.close()
    _client = None
    _db = None


def reset_client() -> None:
    """Drop cached client so a fresh one binds to the current event loop.
    Called at the start of the FastAPI lifespan to make tests that spin up
    multiple TestClient instances safe."""
    global _client, _db
    if _client is not None:
        try:
            _client.close()
        except Exception:
            pass
    _client = None
    _db = None


async def ensure_indexes() -> None:
    """Create indexes required for Phase 1 (auth + tenancy) and Phase 2 (ingestion/radar)."""
    db = get_db()

    # users
    await db.users.create_index("email", unique=True)
    await db.users.create_index([("enterprise_id", 1), ("role", 1)])

    # enterprises
    await db.enterprises.create_index("name", unique=True)
    await db.enterprises.create_index("is_demo")

    # enterprise_settings
    await db.enterprise_settings.create_index("enterprise_id", unique=True)

    # brute-force
    await db.login_attempts.create_index("identifier")
    await db.login_attempts.create_index("expires_at", expireAfterSeconds=0)

    # audit
    await db.audit_logs.create_index([("enterprise_id", 1), ("at", -1)])

    # Phase 2 --------------------------------------------------------
    await db.transactions.create_index([("enterprise_id", 1), ("order_date", -1)])
    await db.transactions.create_index([("enterprise_id", 1), ("outlet_code", 1), ("order_date", -1)])
    await db.transactions.create_index([("enterprise_id", 1), ("distributor_code", 1), ("order_date", -1)])
    await db.transactions.create_index(
        [("enterprise_id", 1), ("distributor_code", 1), ("row_hash", 1)],
        unique=True,
    )
    await db.import_batches.create_index([("enterprise_id", 1), ("file_hash", 1)], unique=True)
    await db.import_batches.create_index([("enterprise_id", 1), ("started_at", -1)])
    await db.opportunities.create_index([("enterprise_id", 1), ("priority_score", -1)])
    await db.opportunities.create_index([("enterprise_id", 1), ("type", 1)])
    await db.opportunities.create_index([("enterprise_id", 1), ("distributor_code", 1), ("outlet_code", 1)])
    await db.targets.create_index([("enterprise_id", 1), ("period_month", 1), ("target_scope_type", 1)])

    # Phase 3 -------------------------------------------------------
    await db.actions.create_index([("enterprise_id", 1), ("salesperson_code", 1), ("status", 1)])
    await db.actions.create_index([("enterprise_id", 1), ("outlet_code", 1), ("assigned_at", -1)])
    await db.actions.create_index("expires_at", expireAfterSeconds=0)
    await db.recoveries.create_index(
        [("enterprise_id", 1), ("distributor_code", 1), ("outlet_code", 1), ("invoice_no", 1)],
        unique=True,
    )
    await db.recoveries.create_index("expires_at", expireAfterSeconds=0)
